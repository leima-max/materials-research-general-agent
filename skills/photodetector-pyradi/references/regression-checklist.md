# photodetector-pyradi regression checklist

Use this checklist after any of the following:
- vendor pruning
- dependency reinstall or upgrade
- changes to `compute_detector_metrics.py`
- changes to demo data or config schema
- packaging before release

## release gate

A release is considered healthy only if all items below pass.

## must-pass functional checks

### 1. measured-noise path
Run:
- `python scripts/generate_demo_dataset.py`
- `python scripts/compute_detector_metrics.py --config assets/demo/demo_config_measured_noise.json`

Expect:
- command exits successfully
- summary json is created
- metrics csv is created
- QE png is created
- responsivity png is created
- D* png is created
- `noise_mode == "measured_density_to_rms"`
- `qe_input_mode == "percent"`

### 2. shot-noise path
Run:
- `python scripts/compute_detector_metrics.py --config assets/demo/demo_config_shot_noise.json`

Expect:
- command exits successfully
- summary json is created
- metrics csv is created
- `noise_mode == "shot_noise_from_dark_current"`
- D* peak is present

### 3. vendor-pruning compatibility
Run after `scripts/prune_vendor.py` if vendor changes were made.

Expect:
- both checks above still pass
- no import error from `numpy`, `scipy`, `matplotlib`, or `pyradi`
- specifically watch for failures related to `numpy._core.tests._natype`

## artifact checks

Confirm these files exist after smoke tests:
- `assets/demo/outputs_measured_noise/device_a_measured_noise_summary.json`
- `assets/demo/outputs_shot_noise/device_a_shot_noise_summary.json`
- corresponding csv and png files

## non-goals of this checklist

This checklist does not prove:
- every possible CSV schema variation works
- every pyradi helper outside `rydetector` works
- every plotting backend or font path works

It is intentionally scoped to the skill's supported primary workflow.

## release note template

- measured-noise demo: pass/fail
- shot-noise demo: pass/fail
- vendor-pruned runtime: pass/fail
- packaged skill rebuilt: yes/no
- package size: <value>
