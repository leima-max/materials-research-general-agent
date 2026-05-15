# xrd-pyfai reporting playbook

Use this file when you need to choose the right pyFAI reduction mode, sanity-check geometry, or turn outputs into a materials interpretation.

## 1. choose the mode

### A. mode = `1d`
Use when the goal is:
- inspect phase-related peaks
- compare integrated intensity profiles
- pass clean data to later peak fitting

### B. mode = `2d`
Use when the goal is:
- inspect texture anisotropy
- show arcs, spots, rings, or ring continuity
- compare in-plane / out-of-plane scattering character qualitatively

### C. mode = `azimuthal`
Use when the goal is:
- quantify orientation spread in a selected radial window
- extract an azimuthal FWHM for texture comparison

## 2. geometry sanity checks before trusting the output

Check all of these:
- the `.poni` file belongs to the same beamline/instrument setup
- beam center and detector distance are plausible for the experiment
- image dimensions match the correction arrays
- the selected unit (`2th_deg` or `q_A^-1`) matches the downstream interpretation
- the chosen radial window overlaps an actual diffraction feature

If any of these are unclear, treat the output as provisional.

## 3. what the script actually returns

### `1d`
- `<label>_1d.csv`
- `<label>_1d.png`
- `<label>_summary.json`
- summary includes auto-detected prominent peaks

### `2d`
- `<label>_cake.npz`
- `<label>_cake.png`
- `<label>_summary.json`
- summary includes intensity-map shape and applied corrections

### `azimuthal`
- `<label>_azimuthal.csv`
- `<label>_azimuthal.png`
- `<label>_summary.json`
- summary includes `profile_radial_range` and `profile_stats.fwhm`

## 4. minimum reporting items

Always include:
- raw image name
- `.poni` used
- mode used
- integration unit
- radial range / azimuth range if applied
- whether mask, dark, and flat corrections were applied
- for azimuthal mode: the radial window and extracted FWHM

## 5. interpretation templates

### 1D curve
- "The pyFAI-reduced 1D profile reveals the principal diffraction features in <unit>, providing a preprocessing-ready curve for phase comparison and subsequent peak fitting."

### 2D cake plot
- "The 2D cake map preserves the angular intensity distribution, allowing direct inspection of arc continuity, ring anisotropy, and texture-related scattering features that are lost in pure 1D integration."

### azimuthal profile
- "The azimuthal profile extracted from <radial_window> shows a texture-distribution FWHM of <fwhm>, which can be used for relative orientation comparison across samples measured under the same geometry and reduction settings."

## 6. common pitfalls

- Using the wrong `.poni` file from a different sample-detector distance
- Comparing samples reduced with different `npt`, units, or radial windows
- Choosing an azimuthal window dominated by background rather than diffraction intensity
- Over-interpreting narrow azimuthal FWHM as proof of interface registry without reciprocal-space context, HRTEM/FFT, or phi-scan evidence
- Forgetting that 1D integration can hide texture information visible in the 2D pattern

## 7. Guidance For Texture And Orientation Discussions

For configured thin films, layered samples, or other anisotropic materials:
- Use `2d` output to inspect whether intensity forms arcs/spots rather than isotropic rings.
- Use `azimuthal` FWHM as a **texture-strength metric**, not a stand-alone proof of long-range registry.
- Combine pyFAI outputs with complementary structural evidence before making strong ordering claims.
- If the 2D pattern is diffuse or strongly broadened, discuss disorder, mosaicity, grain spread, or mixed orientation instead of forcing an ordering narrative.


