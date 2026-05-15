#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
DEMO_DIR = SKILL_DIR / "assets" / "demo"


def main() -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = DEMO_DIR / "spectral_device_a.csv"
    rows = [
        (0.45, 12.1, 2.10e-14),
        (0.50, 18.4, 2.00e-14),
        (0.55, 25.6, 1.92e-14),
        (0.60, 31.4, 1.85e-14),
        (0.65, 36.8, 1.80e-14),
        (0.70, 42.7, 1.76e-14),
        (0.80, 51.8, 1.70e-14),
        (0.90, 58.9, 1.66e-14),
        (1.00, 63.1, 1.72e-14),
        (1.10, 60.7, 1.85e-14),
        (1.20, 54.2, 2.05e-14),
        (1.30, 46.0, 2.28e-14),
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["wavelength_um", "qe_percent", "noise_a_root_hz"])
        writer.writerows(rows)

    measured_cfg = {
        "input_csv": "spectral_device_a.csv",
        "wavelength_column": "wavelength_um",
        "qe_column": "qe_percent",
        "noise_density_column": "noise_a_root_hz",
        "bandwidth_hz": 1.0,
        "area_cm2": 0.01,
        "output_dir": "outputs_measured_noise",
        "label": "device_a_measured_noise"
    }
    shot_cfg = {
        "input_csv": "spectral_device_a.csv",
        "wavelength_column": "wavelength_um",
        "qe_column": "qe_percent",
        "dark_current_a": 3.2e-9,
        "bandwidth_hz": 100.0,
        "area_cm2": 0.01,
        "output_dir": "outputs_shot_noise",
        "label": "device_a_shot_noise"
    }

    (DEMO_DIR / "demo_config_measured_noise.json").write_text(json.dumps(measured_cfg, indent=2), encoding="utf-8")
    (DEMO_DIR / "demo_config_shot_noise.json").write_text(json.dumps(shot_cfg, indent=2), encoding="utf-8")

    result = {
        "status": "ok",
        "demo_dir": str(DEMO_DIR),
        "files": [
            str(csv_path),
            str(DEMO_DIR / "demo_config_measured_noise.json"),
            str(DEMO_DIR / "demo_config_shot_noise.json"),
        ],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
