#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = SKILL_DIR / "vendor" / "site-packages"
if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

import numpy as np
from pyFAI.integrator.azimuthal import AzimuthalIntegrator

DEMO_DIR = SKILL_DIR / "assets" / "demo"


def build_synthetic_pattern(size: int = 512, pixel_m: float = 1e-4, distance_m: float = 0.035) -> np.ndarray:
    yy, xx = np.indices((size, size), dtype=float)
    center = (size - 1) / 2.0
    dx = (xx - center) * pixel_m
    dy = (yy - center) * pixel_m
    rr = np.sqrt(dx**2 + dy**2)
    tt_deg = np.degrees(np.arctan2(rr, distance_m))
    phi = np.degrees(np.arctan2(dy, dx))

    ring1 = 900.0 * np.exp(-0.5 * ((tt_deg - 12.0) / 0.45) ** 2)
    ring2_base = 700.0 * np.exp(-0.5 * ((tt_deg - 24.0) / 0.55) ** 2)
    ring3 = 450.0 * np.exp(-0.5 * ((tt_deg - 35.0) / 0.70) ** 2)

    arc_a = np.exp(-0.5 * ((phi - 30.0) / 16.0) ** 2)
    arc_b = np.exp(-0.5 * ((phi + 150.0) / 16.0) ** 2)
    textured_ring2 = ring2_base * (0.15 + 1.7 * (arc_a + arc_b))

    background = 40.0 + 8.0 * np.exp(-tt_deg / 20.0)
    noise = np.random.default_rng(7).normal(loc=0.0, scale=6.0, size=(size, size))
    image = background + ring1 + textured_ring2 + ring3 + noise
    return np.clip(image, 0, None).astype(np.float32)


def main() -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    size = 512
    pixel_m = 1e-4
    distance_m = 0.035
    center_m = ((size - 1) / 2.0) * pixel_m
    wavelength_m = 1.5406e-10

    image = build_synthetic_pattern(size=size, pixel_m=pixel_m, distance_m=distance_m)
    image_path = DEMO_DIR / "synthetic_texture_image.npy"
    np.save(image_path, image)

    ai = AzimuthalIntegrator(
        dist=distance_m,
        poni1=center_m,
        poni2=center_m,
        pixel1=pixel_m,
        pixel2=pixel_m,
        wavelength=wavelength_m,
    )
    poni_path = DEMO_DIR / "synthetic_texture.poni"
    ai.save(str(poni_path))

    config_1d = {
        "image_path": "synthetic_texture_image.npy",
        "poni_path": "synthetic_texture.poni",
        "output_dir": "outputs_1d",
        "mode": "1d",
        "label": "synthetic_texture",
        "unit": "2th_deg",
        "npt": 1800,
    }
    config_2d = {
        "image_path": "synthetic_texture_image.npy",
        "poni_path": "synthetic_texture.poni",
        "output_dir": "outputs_2d",
        "mode": "2d",
        "label": "synthetic_texture",
        "unit": "2th_deg",
        "npt_rad": 700,
        "npt_azim": 360,
    }
    config_az = {
        "image_path": "synthetic_texture_image.npy",
        "poni_path": "synthetic_texture.poni",
        "output_dir": "outputs_azimuthal",
        "mode": "azimuthal",
        "label": "synthetic_texture",
        "unit": "2th_deg",
        "npt_rad": 700,
        "npt_azim": 360,
        "profile_radial_range": [23.0, 25.0]
    }

    (DEMO_DIR / "demo_config_1d.json").write_text(json.dumps(config_1d, indent=2), encoding="utf-8")
    (DEMO_DIR / "demo_config_2d.json").write_text(json.dumps(config_2d, indent=2), encoding="utf-8")
    (DEMO_DIR / "demo_config_azimuthal.json").write_text(json.dumps(config_az, indent=2), encoding="utf-8")

    result = {
        "status": "ok",
        "demo_dir": str(DEMO_DIR),
        "files": [
            str(image_path),
            str(poni_path),
            str(DEMO_DIR / "demo_config_1d.json"),
            str(DEMO_DIR / "demo_config_2d.json"),
            str(DEMO_DIR / "demo_config_azimuthal.json"),
        ],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
