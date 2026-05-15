# xrd-pyfai regression checklist

Use this checklist after any of the following:
- vendor pruning
- dependency reinstall or upgrade
- changes to `integrate_xrd.py`
- changes to synthetic demo geometry or configs
- packaging before release

## release gate

A release is considered healthy only if all items below pass.

## must-pass functional checks

### 1. 1D integration
Run:
- `python scripts/generate_demo_dataset.py`
- `python scripts/integrate_xrd.py --config assets/demo/demo_config_1d.json`

Expect:
- command exits successfully
- 1D csv and png are created
- summary json is created
- summary contains at least one detected peak

### 2. 2D cake integration
Run:
- `python scripts/integrate_xrd.py --config assets/demo/demo_config_2d.json`

Expect:
- command exits successfully
- cake npz and png are created
- summary json is created
- summary contains `shape`

### 3. azimuthal profile extraction
Run:
- `python scripts/integrate_xrd.py --config assets/demo/demo_config_azimuthal.json`

Expect:
- command exits successfully
- azimuthal csv and png are created
- summary json is created
- `profile_radial_range` is present
- `profile_stats.fwhm` is present and not null

### 4. vendor-pruning compatibility
Run after `scripts/prune_vendor.py` if vendor changes were made.

Expect:
- all three checks above still pass
- no import error from `numpy`, `scipy`, `fabio`, `pyFAI`, or `matplotlib`
- no geometry-overlap error for the bundled azimuthal demo

## artifact checks

Confirm these files exist after smoke tests:
- `assets/demo/outputs_1d/synthetic_texture_summary.json`
- `assets/demo/outputs_2d/synthetic_texture_summary.json`
- `assets/demo/outputs_azimuthal/synthetic_texture_summary.json`

## non-goals of this checklist

This checklist does not prove:
- every detector format supported by fabio works
- GUI-related pyFAI or silx features work
- every optional correction path or advanced unit conversion path works

It is intentionally scoped to the skill's supported primary workflow.

## release note template

- 1D demo: pass/fail
- 2D demo: pass/fail
- azimuthal demo: pass/fail
- vendor-pruned runtime: pass/fail
- packaged skill rebuilt: yes/no
- package size: <value>
