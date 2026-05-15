# photodetector-pyradi input schema

Use `scripts/compute_detector_metrics.py --config <config.json>`.

## Required keys

```json
{
  "input_csv": "absolute/or/relative/path/to/spectral_data.csv",
  "wavelength_column": "wavelength_um",
  "output_dir": "absolute/or/relative/path/to/output_dir"
}
```

## Supported keys

```json
{
  "input_csv": "device_a.csv",
  "wavelength_column": "wavelength_um",
  "qe_column": "qe",
  "responsivity_column": null,
  "noise_rms_column": null,
  "noise_density_column": "noise_a_root_hz",
  "dark_current_a": 1e-9,
  "bandwidth_hz": 1.0,
  "area_cm2": 0.01,
  "output_dir": "outputs/device_a",
  "label": "device_a",
  "wavelength_min_um": null,
  "wavelength_max_um": null
}
```

## Rules

- Input csv must contain a wavelength column in **µm**.
- Provide either:
  - `qe_column`, or
  - `responsivity_column`, or
  - both.
- For D* / NEP, provide one of:
  - `noise_rms_column`,
  - `noise_density_column` together with `bandwidth_hz`,
  - `dark_current_a` together with `bandwidth_hz` for shot-noise-limited estimation.
- `qe_column` may be either 0–1 fraction or 0–100 percent. The script auto-detects and records the assumption.
- `area_cm2` is detector active area in **cm²**.

## Example input csv

```csv
wavelength_um,qe,noise_a_root_hz
0.45,12.1,2.1e-14
0.50,18.4,2.0e-14
0.55,25.6,1.9e-14
0.60,29.8,1.8e-14
```

## Example config: QE + measured noise density

```json
{
  "input_csv": "data/device_a.csv",
  "wavelength_column": "wavelength_um",
  "qe_column": "qe",
  "noise_density_column": "noise_a_root_hz",
  "bandwidth_hz": 1.0,
  "area_cm2": 0.01,
  "output_dir": "outputs/device_a",
  "label": "device_a"
}
```

## Example config: responsivity only + dark current estimate

```json
{
  "input_csv": "data/device_b.csv",
  "wavelength_column": "wavelength_um",
  "responsivity_column": "responsivity_A_W",
  "dark_current_a": 3.2e-9,
  "bandwidth_hz": 100.0,
  "area_cm2": 0.0025,
  "output_dir": "outputs/device_b",
  "label": "device_b"
}
```
