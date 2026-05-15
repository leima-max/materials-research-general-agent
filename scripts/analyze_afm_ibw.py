#!/usr/bin/env python
"""Analyze AFM Igor Binary Wave files exported from Asylum/Igor.

The pipeline uses the HeightRetrace channel, applies global plane leveling
followed by row-wise first-order flattening, then reports areal roughness and
simple grain/island statistics.
"""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from igor2 import binarywave
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.measure import regionprops_table
from skimage.segmentation import watershed


@dataclass
class AfmRecord:
    path: Path
    stem: str
    data: np.ndarray
    labels: list[str]
    note: dict[str, str]
    scan_size_m: float
    pixel_size_m: float
    height_index: int


def parse_note(raw: bytes | str) -> dict[str, str]:
    if isinstance(raw, bytes):
        text = raw.decode("latin1", errors="replace")
    else:
        text = raw
    out: dict[str, str] = {}
    for part in re.split(r"[\r\n]+", text):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        out[key.strip()] = value.strip()
    return out


def to_float(value: str | None, default: float = math.nan) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def load_afm(path: Path) -> AfmRecord:
    wave = binarywave.load(str(path))["wave"]
    data = np.asarray(wave["wData"], dtype=float)
    labels_raw = wave.get("labels", [[], [], [], []])[2]
    labels = []
    for item in labels_raw[1:]:
        if isinstance(item, bytes):
            labels.append(item.decode("latin1", errors="replace"))
        else:
            labels.append(str(item))
    note = parse_note(wave.get("note", b""))
    scan_size_m = to_float(note.get("ScanSize"))
    if not np.isfinite(scan_size_m):
        sf_a = np.asarray(wave["wave_header"]["sfA"], dtype=float)
        n_dim = np.asarray(wave["wave_header"]["nDim"], dtype=int)
        scan_size_m = float(sf_a[0] * max(n_dim[0] - 1, 1))
    pixel_size_m = scan_size_m / max(data.shape[0] - 1, 1)
    height_index = 0
    for idx, label in enumerate(labels):
        if "height" in label.lower():
            height_index = idx
            break
    return AfmRecord(path, path.stem, data, labels, note, scan_size_m, pixel_size_m, height_index)


def robust_plane_level(z_nm: np.ndarray) -> np.ndarray:
    ny, nx = z_nm.shape
    yy, xx = np.mgrid[:ny, :nx]
    lo, hi = np.nanpercentile(z_nm, [2, 98])
    mask = np.isfinite(z_nm) & (z_nm >= lo) & (z_nm <= hi)
    a = np.column_stack([xx[mask].ravel(), yy[mask].ravel(), np.ones(mask.sum())])
    coeff, *_ = np.linalg.lstsq(a, z_nm[mask].ravel(), rcond=None)
    plane = coeff[0] * xx + coeff[1] * yy + coeff[2]
    return z_nm - plane


def row_flatten(z_nm: np.ndarray) -> np.ndarray:
    ny, nx = z_nm.shape
    x = np.arange(nx, dtype=float)
    out = np.empty_like(z_nm, dtype=float)
    for row_idx in range(ny):
        row = z_nm[row_idx]
        lo, hi = np.nanpercentile(row, [5, 95])
        mask = np.isfinite(row) & (row >= lo) & (row <= hi)
        if mask.sum() >= 3:
            coeff = np.polyfit(x[mask], row[mask], 1)
            out[row_idx] = row - np.polyval(coeff, x)
        else:
            out[row_idx] = row - np.nanmedian(row)
    return out - np.nanmedian(out)


def roughness_metrics(z_nm: np.ndarray, scan_size_um: float, pixel_size_nm: float) -> dict[str, float]:
    z = z_nm[np.isfinite(z_nm)]
    z0 = z - np.mean(z)
    sq = float(np.sqrt(np.mean(z0**2)))
    if sq > 0:
        ssk = float(np.mean((z0 / sq) ** 3))
        sku = float(np.mean((z0 / sq) ** 4))
    else:
        ssk = math.nan
        sku = math.nan
    return {
        "scan_size_um": scan_size_um,
        "pixel_size_nm": pixel_size_nm,
        "Sa_Ra_nm": float(np.mean(np.abs(z0))),
        "Sq_Rq_nm": sq,
        "Sp_nm": float(np.max(z0)),
        "Sv_nm": float(-np.min(z0)),
        "Sz_nm": float(np.max(z0) - np.min(z0)),
        "Ssk": ssk,
        "Sku": sku,
        "P05_nm": float(np.percentile(z0, 5)),
        "P50_nm": float(np.percentile(z0, 50)),
        "P95_nm": float(np.percentile(z0, 95)),
        "corr_len_1e_nm": autocorr_length_nm(z0.reshape(z_nm.shape), pixel_size_nm),
    }


def autocorr_length_nm(z_nm: np.ndarray, pixel_size_nm: float) -> float:
    z = np.nan_to_num(z_nm - np.nanmean(z_nm), nan=0.0)
    f = np.fft.fft2(z)
    ac = np.fft.ifft2(f * np.conj(f)).real
    ac = np.fft.fftshift(ac)
    center = tuple(s // 2 for s in ac.shape)
    if ac[center] == 0:
        return math.nan
    ac /= ac[center]
    yy, xx = np.indices(ac.shape)
    r = np.sqrt((xx - center[1]) ** 2 + (yy - center[0]) ** 2)
    r_int = r.astype(int)
    max_r = min(center)
    radial = np.bincount(r_int.ravel(), ac.ravel(), minlength=max_r + 1)
    counts = np.bincount(r_int.ravel(), minlength=max_r + 1)
    radial = radial[: max_r + 1] / np.maximum(counts[: max_r + 1], 1)
    below = np.flatnonzero(radial < math.exp(-1))
    if below.size == 0:
        return math.nan
    idx = int(below[0])
    return float(idx * pixel_size_nm)


def grain_stats(z_nm: np.ndarray, pixel_size_nm: float, min_area_px: int = 8) -> tuple[pd.DataFrame, np.ndarray]:
    smooth = ndi.gaussian_filter(z_nm, sigma=1.0)
    coords = peak_local_max(smooth, min_distance=4, threshold_abs=np.percentile(smooth, 55), exclude_border=False)
    markers = np.zeros(smooth.shape, dtype=int)
    if len(coords) == 0:
        labels = np.ones(smooth.shape, dtype=int)
    else:
        markers[tuple(coords.T)] = np.arange(1, len(coords) + 1)
        mask = smooth > np.percentile(smooth, 5)
        labels = watershed(-smooth, markers, mask=mask)
    props = regionprops_table(
        labels,
        intensity_image=z_nm,
        properties=("label", "area", "equivalent_diameter_area", "mean_intensity", "max_intensity", "min_intensity"),
    )
    df = pd.DataFrame(props)
    if df.empty:
        return df, labels
    df = df[df["area"] >= min_area_px].copy()
    df["area_um2"] = df["area"] * (pixel_size_nm / 1000.0) ** 2
    df["equiv_diameter_nm"] = df["equivalent_diameter_area"] * pixel_size_nm
    df["height_relief_nm"] = df["max_intensity"] - df["min_intensity"]
    return df, labels


def save_height_plot(stem: str, z_nm: np.ndarray, scan_size_um: float, out_dir: Path) -> None:
    extent = [0, scan_size_um, 0, scan_size_um]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.7), constrained_layout=True)
    im = axes[0].imshow(z_nm, cmap="viridis", extent=extent, origin="lower")
    axes[0].set_title(f"{stem} height")
    axes[0].set_xlabel("x (um)")
    axes[0].set_ylabel("y (um)")
    cb = fig.colorbar(im, ax=axes[0], fraction=0.046, pad=0.04)
    cb.set_label("height (nm)")
    axes[1].hist(z_nm.ravel(), bins=80, color="#4c78a8", edgecolor="none")
    axes[1].set_title("Height distribution")
    axes[1].set_xlabel("height (nm)")
    axes[1].set_ylabel("pixels")
    fig.savefig(out_dir / f"{stem}_height_flattened.png", dpi=250)
    plt.close(fig)


def save_channel_plot(record: AfmRecord, z_flat_nm: np.ndarray, out_dir: Path) -> None:
    scan_size_um = record.scan_size_m * 1e6
    extent = [0, scan_size_um, 0, scan_size_um]
    channels = []
    for idx, label in enumerate(record.labels[: record.data.shape[2]]):
        arr = record.data[:, :, idx]
        if idx == record.height_index:
            channels.append((label or f"channel {idx}", z_flat_nm, "nm"))
        elif "amplitude" in label.lower() or "zsensor" in label.lower():
            channels.append((label or f"channel {idx}", arr * 1e9, "nm"))
        else:
            channels.append((label or f"channel {idx}", arr, "raw"))
    n = len(channels)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 3.6), constrained_layout=True)
    if n == 1:
        axes = [axes]
    for ax, (label, arr, unit) in zip(axes, channels):
        vmin, vmax = np.nanpercentile(arr, [1, 99])
        im = ax.imshow(arr, cmap="viridis", extent=extent, origin="lower", vmin=vmin, vmax=vmax)
        ax.set_title(label)
        ax.set_xlabel("x (um)")
        ax.set_ylabel("y (um)")
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cb.set_label(unit)
    fig.savefig(out_dir / f"{record.stem}_channels.png", dpi=220)
    plt.close(fig)


def save_summary_plot(summary: pd.DataFrame, out_dir: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.5), constrained_layout=True)
    x = np.arange(len(summary))
    labels = summary["file"].to_list()
    for ax, col, title in zip(
        axes,
        ["Sa_Ra_nm", "Sq_Rq_nm", "Sz_nm"],
        ["Sa/Ra", "Sq/Rq", "Sz"],
    ):
        ax.bar(x, summary[col], color="#4c78a8")
        ax.set_xticks(x, labels, rotation=30, ha="right")
        ax.set_ylabel("nm")
        ax.set_title(title)
    fig.savefig(out_dir / "roughness_summary.png", dpi=250)
    plt.close(fig)


def analyze(files: list[Path], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    grain_rows = []
    for path in files:
        record = load_afm(path)
        height_nm = record.data[:, :, record.height_index] * 1e9
        plane_nm = robust_plane_level(height_nm)
        flat_nm = row_flatten(plane_nm)
        scan_size_um = record.scan_size_m * 1e6
        pixel_size_nm = record.pixel_size_m * 1e9
        metrics = roughness_metrics(flat_nm, scan_size_um, pixel_size_nm)
        metrics.update(
            {
                "file": record.path.name,
                "height_channel": record.labels[record.height_index] if record.labels else str(record.height_index),
                "scan_rate_Hz": to_float(record.note.get("ScanRate")),
                "scan_angle_deg": to_float(record.note.get("ScanAngle")),
            }
        )
        summary_rows.append(metrics)

        grains, labels = grain_stats(flat_nm, pixel_size_nm)
        if not grains.empty:
            grains.insert(0, "file", record.path.name)
            grain_rows.append(grains)
        np.savetxt(out_dir / f"{record.stem}_height_flattened_nm.csv", flat_nm, delimiter=",", fmt="%.6f")
        np.save(out_dir / f"{record.stem}_height_flattened_nm.npy", flat_nm)
        save_height_plot(record.stem, flat_nm, scan_size_um, out_dir)
        save_channel_plot(record, flat_nm, out_dir)
        plt.imsave(out_dir / f"{record.stem}_grain_labels.png", labels, cmap="nipy_spectral")

    summary = pd.DataFrame(summary_rows)
    ordered = [
        "file",
        "height_channel",
        "scan_size_um",
        "pixel_size_nm",
        "scan_rate_Hz",
        "scan_angle_deg",
        "Sa_Ra_nm",
        "Sq_Rq_nm",
        "Sp_nm",
        "Sv_nm",
        "Sz_nm",
        "Ssk",
        "Sku",
        "P05_nm",
        "P50_nm",
        "P95_nm",
        "corr_len_1e_nm",
    ]
    summary = summary[ordered]
    summary.to_csv(out_dir / "roughness_summary.csv", index=False)
    save_summary_plot(summary, out_dir)

    if grain_rows:
        grain_all = pd.concat(grain_rows, ignore_index=True)
    else:
        grain_all = pd.DataFrame()
    grain_all.to_csv(out_dir / "grain_regions.csv", index=False)

    report_lines = [
        "# AFM analysis report",
        "",
        "Input files:",
        *[f"- {path}" for path in files],
        "",
        "Processing:",
        "- Channel: HeightRetrace when available.",
        "- Leveling: robust global plane subtraction, then row-wise first-order flattening.",
        "- Units: height in nm; lateral size from ScanSize metadata.",
        "",
        "Roughness summary:",
        "",
        summary.to_markdown(index=False, floatfmt=".3f"),
        "",
    ]
    if not grain_all.empty:
        grain_summary = (
            grain_all.groupby("file")
            .agg(
                regions=("label", "count"),
                median_equiv_diameter_nm=("equiv_diameter_nm", "median"),
                mean_equiv_diameter_nm=("equiv_diameter_nm", "mean"),
                median_area_um2=("area_um2", "median"),
                median_height_relief_nm=("height_relief_nm", "median"),
            )
            .reset_index()
        )
        grain_summary.to_csv(out_dir / "grain_summary.csv", index=False)
        report_lines.extend(
            [
                "Grain/island segmentation summary:",
                "",
                grain_summary.to_markdown(index=False, floatfmt=".3f"),
                "",
                "Note: segmentation is topography-based and should be treated as an island/grain proxy, not crystallographic grain size.",
                "",
            ]
        )
    (out_dir / "AFM_analysis_report.md").write_text("\n".join(report_lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze AFM IBW files.")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("-o", "--out-dir", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.files, args.out_dir)


if __name__ == "__main__":
    main()
