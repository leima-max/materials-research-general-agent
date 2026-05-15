# xrd-pyfai input schema

Use `scripts/integrate_xrd.py --config <config.json>`.

## Required keys

```json
{
  "image_path": "absolute/or/relative/path/to/raw_image.tif",
  "poni_path": "absolute/or/relative/path/to/geometry.poni",
  "output_dir": "absolute/or/relative/path/to/output_dir",
  "mode": "1d"
}
```

## Supported keys

```json
{
  "image_path": "sample_001.tif",
  "poni_path": "calibration/sample.poni",
  "output_dir": "outputs/sample_001",
  "mode": "1d",
  "label": "sample_001",
  "unit": "2th_deg",
  "npt": 2000,
  "npt_rad": 800,
  "npt_azim": 360,
  "mask_path": null,
  "dark_path": null,
  "flat_path": null,
  "polarization_factor": null,
  "radial_range": [10.0, 40.0],
  "azimuth_range": [-90.0, 90.0],
  "profile_radial_range": [14.2, 15.8]
}
```

## Notes

- `mode`:
  - `1d` → saves radial intensity csv + png + summary json
  - `2d` → saves cake plot png + compressed npz + summary json
  - `azimuthal` → saves azimuthal profile csv + png + summary json
- `unit`: pass a pyFAI unit string such as `2th_deg` or `q_A^-1`
- `radial_range`: interpreted in the selected `unit`
- `profile_radial_range`: only used in `azimuthal` mode; if omitted, `radial_range` is reused
- `mask_path`, `dark_path`, and `flat_path` may be `.npy` arrays or fabio-readable image files

## Example: 1D integration

```json
{
  "image_path": "data/<configure_material_or_component_a>_001.tif",
  "poni_path": "calib/<configure_material_or_component_a>.poni",
  "output_dir": "outputs/<configure_material_or_component_a>_001_1d",
  "mode": "1d",
  "unit": "q_A^-1",
  "npt": 2500
}
```

## Example: azimuthal texture profile

```json
{
  "image_path": "data/<configure_material_or_component_b>_giwaxs.edf",
  "poni_path": "calib/giwaxs.poni",
  "output_dir": "outputs/<configure_material_or_component_b>_texture",
  "mode": "azimuthal",
  "unit": "q_A^-1",
  "npt_rad": 900,
  "npt_azim": 720,
  "profile_radial_range": [1.02, 1.10]
}
```


