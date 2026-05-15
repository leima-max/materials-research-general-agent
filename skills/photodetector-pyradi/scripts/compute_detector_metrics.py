#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
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

import pyradi.rydetector as rydetector

Q = 1.602176634e-19
HC_OVER_Q_UM = 1.2398419843320026


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_config_path(config_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else config_path.parent / path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _col(rows: list[dict[str, str]], name: str | None) -> np.ndarray | None:
    if not name:
        return None
    values = []
    for row in rows:
        raw = row.get(name)
        if raw is None or raw == "":
            values.append(np.nan)
        else:
            values.append(float(raw))
    return np.asarray(values, dtype=float)


def _maybe_percent_to_fraction(qe: np.ndarray) -> tuple[np.ndarray, str]:
    finite = qe[np.isfinite(qe)]
    if finite.size == 0:
        return qe, "unknown"
    if float(np.nanmax(finite)) > 1.2:
        return qe / 100.0, "percent"
    return qe, "fraction"


def _plot_metric(x: np.ndarray, y: np.ndarray, xlabel: str, ylabel: str, title: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(x, y, lw=1.4)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out, dpi=220)
    plt.close(fig)


def _summary_peak(x: np.ndarray, y: np.ndarray) -> dict[str, float | None]:
    if y is None or x.size == 0:
        return {"wavelength_um": None, "value": None}
    valid = np.isfinite(x) & np.isfinite(y)
    if not np.any(valid):
        return {"wavelength_um": None, "value": None}
    idx = int(np.nanargmax(y[valid]))
    xv = x[valid][idx]
    yv = y[valid][idx]
    return {"wavelength_um": float(xv), "value": float(yv)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute spectral photodetector metrics with pyradi rydetector")
    parser.add_argument("--config", required=True, help="Path to JSON config")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    cfg = _load_json(config_path)
    input_csv = _resolve_config_path(config_path, cfg["input_csv"])
    rows = _read_csv(input_csv)
    wavelength = _col(rows, cfg["wavelength_column"])
    if wavelength is None:
        raise ValueError("wavelength_column is required")

    wavelength_min = cfg.get("wavelength_min_um")
    wavelength_max = cfg.get("wavelength_max_um")
    selector = np.ones_like(wavelength, dtype=bool)
    if wavelength_min is not None:
        selector &= wavelength >= float(wavelength_min)
    if wavelength_max is not None:
        selector &= wavelength <= float(wavelength_max)

    wavelength = wavelength[selector]
    qe_raw = _col(rows, cfg.get("qe_column"))
    responsivity_raw = _col(rows, cfg.get("responsivity_column"))
    noise_rms_raw = _col(rows, cfg.get("noise_rms_column"))
    noise_density_raw = _col(rows, cfg.get("noise_density_column"))

    qe = qe_raw[selector] if qe_raw is not None else None
    responsivity = responsivity_raw[selector] if responsivity_raw is not None else None
    noise_rms = noise_rms_raw[selector] if noise_rms_raw is not None else None
    noise_density = noise_density_raw[selector] if noise_density_raw is not None else None

    if qe is None and responsivity is None:
        raise ValueError("Provide qe_column or responsivity_column")

    qe_input_mode = None
    if qe is not None:
        qe, qe_input_mode = _maybe_percent_to_fraction(qe)

    if responsivity is None and qe is not None:
        responsivity = np.asarray(
            rydetector.Responsivity((wavelength * 1e-6).reshape(-1, 1), qe.reshape(-1, 1))
        ).reshape(-1)

    if qe is None and responsivity is not None:
        qe = responsivity * HC_OVER_Q_UM / wavelength

    bandwidth_hz = float(cfg.get("bandwidth_hz", 1.0))
    dark_current_a = cfg.get("dark_current_a")
    noise_mode = None

    if noise_rms is not None:
        noise_mode = "measured_rms"
    elif noise_density is not None:
        noise_rms = noise_density * math.sqrt(bandwidth_hz)
        noise_mode = "measured_density_to_rms"
    elif dark_current_a is not None:
        shot_noise_rms = math.sqrt(2.0 * Q * float(dark_current_a) * bandwidth_hz)
        noise_rms = np.full_like(wavelength, shot_noise_rms, dtype=float)
        noise_mode = "shot_noise_from_dark_current"

    dstar = None
    nep = None
    detectivity = None
    area_cm2 = cfg.get("area_cm2")
    area_m2 = None
    if area_cm2 is not None:
        area_m2 = float(area_cm2) * 1e-4

    if noise_rms is not None:
        nep, detectivity = rydetector.NEP(noise_rms, responsivity)
        if area_m2 is not None:
            dstar = rydetector.DStar(area_m2, bandwidth_hz, noise_rms, responsivity)

    output_dir = _resolve_config_path(config_path, cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    label = cfg.get("label") or input_csv.stem

    csv_path = output_dir / f"{label}_metrics.csv"
    fields = [
        "wavelength_um",
        "qe_fraction",
        "responsivity_A_W",
    ]
    if noise_rms is not None:
        fields.append("noise_rms_A")
    if nep is not None:
        fields.append("nep_W")
    if detectivity is not None:
        fields.append("detectivity_1_W")
    if dstar is not None:
        fields.append("dstar_cm_sqrtHz_W")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, wl in enumerate(wavelength):
            row = {
                "wavelength_um": float(wl),
                "qe_fraction": float(qe[i]),
                "responsivity_A_W": float(responsivity[i]),
            }
            if noise_rms is not None:
                row["noise_rms_A"] = float(noise_rms[i])
            if nep is not None:
                row["nep_W"] = float(nep[i])
            if detectivity is not None:
                row["detectivity_1_W"] = float(detectivity[i])
            if dstar is not None:
                row["dstar_cm_sqrtHz_W"] = float(dstar[i])
            writer.writerow(row)

    qe_png = output_dir / f"{label}_qe.png"
    resp_png = output_dir / f"{label}_responsivity.png"
    _plot_metric(wavelength, qe, "wavelength (µm)", "QE (fraction)", f"{label} QE", qe_png)
    _plot_metric(wavelength, responsivity, "wavelength (µm)", "responsivity (A/W)", f"{label} responsivity", resp_png)

    artifacts = {
        "csv": str(csv_path.resolve()),
        "qe_png": str(qe_png.resolve()),
        "responsivity_png": str(resp_png.resolve()),
    }

    if dstar is not None:
        dstar_png = output_dir / f"{label}_dstar.png"
        _plot_metric(wavelength, dstar, "wavelength (µm)", "D* (cm√Hz/W)", f"{label} D*", dstar_png)
        artifacts["dstar_png"] = str(dstar_png.resolve())

    summary = {
        "status": "ok",
        "label": label,
        "input_csv": str(input_csv.resolve()),
        "output_dir": str(output_dir.resolve()),
        "qe_input_mode": qe_input_mode,
        "noise_mode": noise_mode,
        "bandwidth_hz": bandwidth_hz,
        "area_cm2": area_cm2,
        "dark_current_a": dark_current_a,
        "artifacts": artifacts,
        "peaks": {
            "qe": _summary_peak(wavelength, qe),
            "responsivity": _summary_peak(wavelength, responsivity),
            "dstar": _summary_peak(wavelength, dstar) if dstar is not None else {"wavelength_um": None, "value": None},
        },
    }

    summary_path = output_dir / f"{label}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
