#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = SKILL_DIR / "vendor" / "site-packages"
if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import find_peaks

import fabio
import pyFAI


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_config_path(config_path: Path, value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else config_path.parent / path


def _load_array(path: str | None) -> np.ndarray | None:
    if not path:
        return None
    src = Path(path)
    if src.suffix.lower() == ".npy":
        return np.load(src)
    return np.asarray(fabio.open(str(src)).data, dtype=float)


def _load_image(path: str) -> np.ndarray:
    src = Path(path)
    if src.suffix.lower() == ".npy":
        return np.asarray(np.load(src), dtype=float)
    return np.asarray(fabio.open(str(src)).data, dtype=float)


def _coerce_range(value: object) -> tuple[float, float] | None:
    if value in (None, "", []):
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Range must be a 2-element list, got: {value!r}")
    return float(value[0]), float(value[1])


def _apply_corrections(image: np.ndarray, dark: np.ndarray | None, flat: np.ndarray | None) -> np.ndarray:
    data = image.astype(float, copy=True)
    if dark is not None:
        data = data - dark
    if flat is not None:
        safe_flat = np.where(flat == 0, 1.0, flat)
        data = data / safe_flat
    return data


def _estimate_fwhm(x: np.ndarray, y: np.ndarray) -> dict:
    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]
    if x.size == 0:
        return {"peak_position": None, "peak_value": None, "fwhm": None}
    y_shift = y - np.nanmin(y)
    peak_idx = int(np.nanargmax(y_shift))
    peak_val = float(y[peak_idx])
    peak_pos = float(x[peak_idx])
    ymax = float(np.nanmax(y_shift))
    if ymax <= 0:
        return {"peak_position": peak_pos, "peak_value": peak_val, "fwhm": None}
    half = ymax / 2.0
    above = np.where(y_shift >= half)[0]
    fwhm = float(x[above[-1]] - x[above[0]]) if above.size >= 2 else None
    return {"peak_position": peak_pos, "peak_value": peak_val, "fwhm": fwhm}


def _save_xy_csv(path: Path, x: np.ndarray, y: np.ndarray, x_label: str, y_label: str) -> None:
    data = np.column_stack([x, y])
    np.savetxt(path, data, delimiter=",", header=f"{x_label},{y_label}", comments="")


def _top_peaks(x: np.ndarray, y: np.ndarray, limit: int = 8) -> list[dict]:
    if x.size < 3:
        return []
    prominence = max(float(np.nanmax(y) - np.nanmin(y)) * 0.03, 1e-12)
    idx, props = find_peaks(y, prominence=prominence)
    if idx.size == 0:
        return []
    scores = props.get("prominences", np.zeros_like(idx, dtype=float))
    order = np.argsort(scores)[::-1][:limit]
    peaks = []
    for ii in order:
        j = int(idx[ii])
        peaks.append({"position": float(x[j]), "intensity": float(y[j]), "prominence": float(scores[ii])})
    return peaks


def _plot_line(x: np.ndarray, y: np.ndarray, xlabel: str, ylabel: str, title: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(x, y, lw=1.3)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def _plot_cake(intensity: np.ndarray, radial: np.ndarray, azimuthal: np.ndarray, title: str, out: Path, radial_label: str) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    im = ax.imshow(
        intensity,
        aspect="auto",
        origin="lower",
        extent=[float(radial[0]), float(radial[-1]), float(azimuthal[0]), float(azimuthal[-1])],
        cmap="viridis",
    )
    ax.set_xlabel(radial_label)
    ax.set_ylabel("azimuth (deg)")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label="intensity")
    fig.tight_layout()
    fig.savefig(out, dpi=220)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Integrate detector XRD images with pyFAI")
    parser.add_argument("--config", required=True, help="Path to JSON config file")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    cfg = _load_json(config_path)
    image_path = _resolve_config_path(config_path, cfg["image_path"])
    poni_path = _resolve_config_path(config_path, cfg["poni_path"])
    output_dir = _resolve_config_path(config_path, cfg["output_dir"])
    assert image_path is not None and poni_path is not None and output_dir is not None
    output_dir.mkdir(parents=True, exist_ok=True)

    label = cfg.get("label") or Path(image_path).stem
    mode = cfg.get("mode", "1d")
    unit = cfg.get("unit", "2th_deg")
    npt = int(cfg.get("npt", 2000))
    npt_rad = int(cfg.get("npt_rad", 800))
    npt_azim = int(cfg.get("npt_azim", 360))
    radial_range = _coerce_range(cfg.get("radial_range"))
    azimuth_range = _coerce_range(cfg.get("azimuth_range"))
    profile_radial_range = _coerce_range(cfg.get("profile_radial_range")) or radial_range
    polarization_factor = cfg.get("polarization_factor")

    image = _load_image(str(image_path))
    mask_path = _resolve_config_path(config_path, cfg.get("mask_path"))
    dark_path = _resolve_config_path(config_path, cfg.get("dark_path"))
    flat_path = _resolve_config_path(config_path, cfg.get("flat_path"))
    mask = _load_array(str(mask_path) if mask_path else None)
    dark = _load_array(str(dark_path) if dark_path else None)
    flat = _load_array(str(flat_path) if flat_path else None)
    corrected = _apply_corrections(image, dark=dark, flat=flat)

    ai = pyFAI.load(str(poni_path))

    summary: dict[str, object] = {
        "status": "ok",
        "mode": mode,
        "label": label,
        "unit": unit,
        "image_path": str(Path(image_path).resolve()),
        "poni_path": str(Path(poni_path).resolve()),
        "output_dir": str(output_dir.resolve()),
        "radial_range": list(radial_range) if radial_range else None,
        "azimuth_range": list(azimuth_range) if azimuth_range else None,
        "corrections": {
            "mask": bool(mask is not None),
            "dark": bool(dark is not None),
            "flat": bool(flat is not None),
        },
        "artifacts": {},
    }

    common_kwargs = {
        "mask": mask,
        "unit": unit,
        "radial_range": radial_range,
        "azimuth_range": azimuth_range,
        "polarization_factor": polarization_factor,
    }

    if mode == "1d":
        res = ai.integrate1d(corrected, npt=npt, **common_kwargs)
        radial = np.asarray(res.radial, dtype=float)
        intensity = np.asarray(res.intensity, dtype=float)
        csv_path = output_dir / f"{label}_1d.csv"
        png_path = output_dir / f"{label}_1d.png"
        _save_xy_csv(csv_path, radial, intensity, unit, "intensity")
        _plot_line(radial, intensity, unit, "intensity", f"{label} 1D integration", png_path)
        summary["artifacts"] = {
            "csv": str(csv_path.resolve()),
            "png": str(png_path.resolve()),
        }
        summary["peaks"] = _top_peaks(radial, intensity)

    elif mode == "2d":
        res = ai.integrate2d(corrected, npt_rad=npt_rad, npt_azim=npt_azim, **common_kwargs)
        radial = np.asarray(res.radial, dtype=float)
        azimuthal = np.asarray(res.azimuthal, dtype=float)
        intensity = np.asarray(res.intensity, dtype=float)
        npz_path = output_dir / f"{label}_cake.npz"
        png_path = output_dir / f"{label}_cake.png"
        np.savez_compressed(npz_path, radial=radial, azimuthal=azimuthal, intensity=intensity)
        _plot_cake(intensity, radial, azimuthal, f"{label} cake plot", png_path, unit)
        summary["artifacts"] = {
            "npz": str(npz_path.resolve()),
            "png": str(png_path.resolve()),
        }
        summary["shape"] = list(intensity.shape)

    elif mode == "azimuthal":
        if profile_radial_range is None:
            raise ValueError("azimuthal mode requires profile_radial_range or radial_range")
        res = ai.integrate2d(corrected, npt_rad=npt_rad, npt_azim=npt_azim, **common_kwargs)
        radial = np.asarray(res.radial, dtype=float)
        azimuthal = np.asarray(res.azimuthal, dtype=float)
        intensity = np.asarray(res.intensity, dtype=float)
        window = (radial >= profile_radial_range[0]) & (radial <= profile_radial_range[1])
        if not np.any(window):
            raise ValueError("Selected profile_radial_range does not overlap the integrated radial axis")
        profile = np.nanmean(intensity[:, window], axis=1)
        csv_path = output_dir / f"{label}_azimuthal.csv"
        png_path = output_dir / f"{label}_azimuthal.png"
        _save_xy_csv(csv_path, azimuthal, profile, "azimuth_deg", "intensity")
        _plot_line(azimuthal, profile, "azimuth (deg)", "intensity", f"{label} azimuthal profile", png_path)
        summary["artifacts"] = {
            "csv": str(csv_path.resolve()),
            "png": str(png_path.resolve()),
        }
        summary["profile_radial_range"] = list(profile_radial_range)
        summary["profile_stats"] = _estimate_fwhm(azimuthal, profile)

    else:
        raise ValueError(f"Unsupported mode: {mode}")

    summary_path = output_dir / f"{label}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
