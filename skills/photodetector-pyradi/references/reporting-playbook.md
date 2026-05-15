# photodetector-pyradi reporting playbook

Use this file when you need to choose the correct calculation path, explain assumptions, or write a concise results section.

## 1. choose the calculation path

### A. QE only
- Compute responsivity from QE.
- Do **not** claim measured NEP or D* unless noise information exists.

### B. responsivity only
- Back-calculate QE.
- State that QE is inferred from responsivity, not directly measured.

### C. QE/responsivity + measured RMS noise
- Best case for spectral NEP.
- D* is valid only if area is known.

### D. QE/responsivity + noise density
- Convert noise density to RMS using the stated bandwidth.
- Always state the bandwidth explicitly.

### E. QE/responsivity + dark current only
- Report shot-noise-limited NEP/D*.
- Do not present this as measured noise performance.

## 2. formulas behind the script

- Responsivity from QE:
  - `R(λ) = QE(λ) * λ(µm) / 1.239841984`
- QE from responsivity:
  - `QE(λ) = R(λ) * 1.239841984 / λ(µm)`
- Shot-noise RMS current:
  - `i_n = sqrt(2 q I_dark Δf)`
- NEP:
  - `NEP = i_n / R`
- D*:
  - `D* = sqrt(A Δf) / NEP`

## 3. minimum reporting items

Always include:
- wavelength range
- whether QE input was treated as fraction or percent
- noise path used (`measured_rms`, `measured_density_to_rms`, or `shot_noise_from_dark_current`)
- detector area
- bandwidth
- peak responsivity and wavelength
- peak D* and wavelength, if available

## 4. recommended wording templates

### measured-noise case
- "Using the measured current-noise data and an active area of <area_cm2> cm² over <bandwidth_hz> Hz bandwidth, the detector reaches a peak D* of <value> cm·Hz^1/2·W^-1 at <wavelength> µm."

### shot-noise-limited case
- "Using the reported dark current and assuming shot-noise-limited behavior over <bandwidth_hz> Hz bandwidth, the estimated peak D* is <value> cm·Hz^1/2·W^-1 at <wavelength> µm. This is an upper-bound estimate rather than a direct noise measurement."

### incomplete-noise case
- "QE and responsivity can be extracted from the spectral data, but NEP/D* cannot be determined reliably because measured noise or a defensible dark-current-plus-bandwidth pair is not available."

## 5. common failure modes

- Wavelength provided in `nm` but labeled as `µm`
- QE percentages treated as fractions
- Bandwidth confused with chopping frequency or lock-in reference frequency
- Detector area taken from substrate area instead of active area
- Dark current measured at a different bias from the reported responsivity

## 6. Interpretation Hints For Configured Multi-Layer Devices

Use with care; these are interpretation prompts, not automatic conclusions.

- High responsivity with weak D* improvement often points to gain accompanied by noise or trap-assisted processes.
- Spectral response changes can reflect the contribution balance between the user-configured layers, interfaces, and collection pathways.
- If D* improves mainly under reverse-bias operation, discuss built-in field strengthening and interfacial carrier extraction, but check dark-current penalty at the same bias.
- If responsivity rises while dark current rises sharply, discuss the leakage-trap tradeoff instead of only highlighting the gain.



