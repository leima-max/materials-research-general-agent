---
name: photodetector-pyradi
description: Analyze wavelength-dependent photodetector performance from CSV data with pyradi's detector-model functions. Use when the task is to convert QE and responsivity, estimate NEP or D* from measured noise or dark-current shot-noise assumptions, compare spectral detector performance, or export reproducible csv/png/json artifacts for device reports and papers. Best for single-pixel or small-area detector datasets; not for TCAD, transient circuit fitting, focal-plane-array noise decomposition, or full radiometric scene modeling.
---

# Photodetector PyRadi

Use this skill when the user has wavelength-resolved detector data and needs a reproducible metric-extraction workflow rather than a hand-calculated one-off answer.

## What this skill does well

- Convert `QE <-> responsivity`
- Estimate spectral `NEP` and `D*`
- Use measured RMS noise, measured noise density, or shot-noise-limited dark-current assumptions
- Export paper-ready intermediate artifacts: `csv + png + summary json`
- Keep assumptions explicit so the result can survive review

## Do not use this skill for

- transient rise/fall fitting
- RC bandwidth modeling
- device transport / drift-diffusion simulation
- focal-plane-array or imaging-system noise budgets
- blackbody scene radiometry unless the skill is extended beyond `rydetector`

## Core workflow

1. **Classify the input**
   - Does the CSV contain `QE`, `responsivity`, or both?
   - Is noise provided as `RMS current noise` or `current-noise density`?
   - If no measured noise exists, is there a trustworthy `dark current` plus `bandwidth` for shot-noise estimation?

2. **Check the minimum physical metadata**
   - wavelength unit must be `um`
   - active area must be in `cm^2`
   - bandwidth must be in `Hz`
   - QE must be identifiable as `fraction` or `percent`

3. **Choose the noise path**
   - `noise_rms_column` -> use directly
   - `noise_density_column + bandwidth_hz` -> convert to RMS
   - `dark_current_a + bandwidth_hz` -> shot-noise-limited estimate only
   - none of the above -> report only `QE / responsivity`; mark `NEP / D*` as unavailable

4. **Prepare config**
   - Follow `references/input-schema.md`
   - Use `references/reporting-playbook.md` for assumption wording and result framing

5. **Run the calculator**
   - `scripts/compute_detector_metrics.py --config <config.json>`

6. **Report the result with assumptions first**
   - noise mode used
   - detector area
   - bandwidth
   - whether QE was interpreted as fraction or percent
   - whether D* is measured-noise-based or shot-noise-limited

## Recommended output style

Always return:
- what was computed
- what could not be computed and why
- peak `QE`, peak `responsivity`, and peak `D*` when available
- the artifact paths
- 1-2 sentences of physical interpretation tied to the device structure

For concise reporting language and common reviewer-safe phrasing, read `references/reporting-playbook.md`.

## Bundled resources

- `scripts/install_pyradi_subset.py` - install a workspace-local `pyradi` subset
- `scripts/compute_detector_metrics.py` - compute spectral QE, responsivity, NEP, and D*
- `scripts/generate_demo_dataset.py` - generate a runnable demo CSV and JSON configs under `assets/demo/`
- `scripts/run_smoke_test.py` - run the minimum regression checks for measured-noise and shot-noise workflows
- `scripts/prune_vendor.py` - remove cache/test/example baggage from the vendored runtime before distribution
- `references/input-schema.md` - config schema and examples
- `references/reporting-playbook.md` - decision rules, formulas, interpretation, and output templates
- `references/regression-checklist.md` - release gate and required regression checks after upgrades or pruning

## Quick demo

If you want a known-good smoke test before using real data:

1. Run `scripts/generate_demo_dataset.py`
2. Run either:
   - `scripts/compute_detector_metrics.py --config assets/demo/demo_config_measured_noise.json`
   - `scripts/compute_detector_metrics.py --config assets/demo/demo_config_shot_noise.json`
3. Inspect the generated outputs under `assets/demo/outputs_*`

The bundled demo dataset uses QE in **percent**, so it also verifies the script's QE-scale auto-detection path.

## Practical checkpoints

Before running, verify all of the following:
- wavelength column is in `um`, not `nm`
- QE values are not silently mixed between `%` and fraction
- `bandwidth_hz` matches the actual noise measurement bandwidth, not the modulation frequency
- `area_cm2` is the electrically active area used in the detectivity definition
- if only dark current is available, clearly label the result as a **shot-noise-limited estimate**, not a measured D*

## Escalation rules

Stop and ask for clarification if:
- wavelength unit is ambiguous
- QE scale is ambiguous and cannot be inferred safely
- the detector area is missing but the user asks for D*
- the user provides noise density without bandwidth
- dark current varies strongly with wavelength or bias and the provided value is obviously not representative

## Backend note

This skill currently vendors `pyradi.rydetector`, which is the right subset for fast detector-metric extraction. If later the workflow needs photon-flux, Planck background, or scene-radiometry support, extend the installer to include additional modules such as `ryplanck.py` or `rypflux.py`.
