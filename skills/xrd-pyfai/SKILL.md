---
name: xrd-pyfai
description: Reduce and analyze raw 2D XRD, GIWAXS, or WAXS detector images with pyFAI. Use when the task starts from detector images plus geometry calibration (.poni) and the goal is 1D radial integration, 2D cake/polar remapping, azimuthal texture profiling, mask/dark/flat correction, or reusable preprocessing artifacts for thin-film diffraction analysis. Especially useful for orientation evidence, texture spread, and image-to-curve preprocessing before downstream peak fitting. Not for Rietveld refinement, structure solution, or fitting already-integrated x-y curves.
---

# XRD PyFAI

Use this skill when the user has **raw diffraction detector images**, not just exported line scans, and needs a reproducible reduction workflow.

## What this skill does well

- Convert `2D detector image -> 1D diffraction curve`
- Export `2D cake / polar maps`
- Extract `azimuthal texture profiles` in a chosen radial window
- Apply `mask`, `dark`, and `flat` corrections
- Produce reusable `csv / npz / png / summary json` outputs for later analysis

## Do not use this skill for

- Rietveld refinement
- full indexing / structure solution from scratch
- fitting already-integrated `.xy`, `.csv`, or Origin traces
- Scherrer / Williamson-Hall analysis as the only task
- final lattice-parameter claims without downstream calibration-aware fitting

## Core workflow

1. **Confirm the input type**
   - raw image path exists
   - image format is fabio-readable (`.tif`, `.tiff`, `.edf`, `.cbf`, `.npy`, etc.)
   - geometry file `.poni` exists and belongs to the same detector setup

2. **Choose the output mode**
   - `1d` -> radial intensity curve for peak inspection or later fitting
   - `2d` -> cake plot / polar remap for texture and anisotropy inspection
   - `azimuthal` -> orientation spread from a physically chosen radial window

3. **Check the reduction metadata**
   - unit is explicit: usually `2th_deg` or `q_A^-1`
   - radial and azimuth ranges are physically meaningful
   - optional corrections (`mask`, `dark`, `flat`) match the same detector geometry and image shape

4. **Prepare config**
   - Follow `references/input-schema.md`
   - Use `references/reporting-playbook.md` for mode selection, geometry sanity checks, and reporting language

5. **Run the reducer**
   - `scripts/integrate_xrd.py --config <config.json>`

6. **Report the output with traceability**
   - mode used
   - unit and integration ranges
   - applied corrections
   - artifact paths
   - if `azimuthal`, include `profile_radial_range` and extracted `FWHM`

## Interpretation guidance

For thin-film, texture, orientation, or interface-ordering questions, do not stop at "here is the integrated curve." Tie the output to the actual materials question:
- `1d` -> phase visibility, preferred orientation hints, background level, later peak-fit readiness
- `2d` -> texture anisotropy, spot/arc continuity, ring broadening, preferred out-of-plane vs in-plane character
- `azimuthal` -> orientation distribution width; smaller FWHM usually indicates stronger texture but is not by itself proof of registry or interface ordering

For practical interpretation patterns and reviewer-safe wording, read `references/reporting-playbook.md`.

## Bundled resources

- `scripts/install_pyfai.py` - install pyFAI into this skill's workspace-local vendor directory
- `scripts/integrate_xrd.py` - run 1D / 2D / azimuthal reductions and export artifacts
- `scripts/generate_demo_dataset.py` - generate a runnable synthetic detector image, matching `.poni`, and demo configs under `assets/demo/`
- `scripts/run_smoke_test.py` - run the minimum regression checks for 1D, 2D, and azimuthal workflows
- `scripts/prune_vendor.py` - remove cache/test/example baggage from the vendored runtime before distribution
- `references/input-schema.md` - accepted config schema and examples
- `references/reporting-playbook.md` - mode-selection rules, sanity checks, interpretation, and reporting templates
- `references/regression-checklist.md` - release gate and required regression checks after upgrades or pruning

## Quick demo

If you want a known-good smoke test before loading real diffraction images:

1. Run `scripts/generate_demo_dataset.py`
2. Run one of:
   - `scripts/integrate_xrd.py --config assets/demo/demo_config_1d.json`
   - `scripts/integrate_xrd.py --config assets/demo/demo_config_2d.json`
   - `scripts/integrate_xrd.py --config assets/demo/demo_config_azimuthal.json`
3. Inspect the generated outputs under `assets/demo/outputs_*`

The synthetic XRD demo intentionally includes concentric rings plus azimuthally enhanced arcs, so all three reduction modes can be verified end-to-end.

## Practical checkpoints

Before running, verify all of the following:
- the `.poni` file matches the detector distance, beam center, and geometry used for the measurement
- image and correction arrays share the same shape
- chosen unit is appropriate for the downstream question
- azimuthal analysis uses a radial window tied to a real diffraction feature, not a background-dominated region
- if comparing samples, keep integration settings consistent across datasets

## Escalation rules

Stop and ask for clarification if:
- `.poni` is missing
- the geometry likely belongs to another detector setup
- the requested azimuthal window does not map to a clear diffraction feature
- the image appears saturated, truncated, or dimension-mismatched with the correction files

If the user instead wants peak fitting, lattice-constant extraction, Scherrer analysis, or Rietveld refinement, use this skill only for preprocessing and then hand the reduced data to a separate downstream workflow.
