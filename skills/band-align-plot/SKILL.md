---
name: band-align-plot
description: Generate publication-ready semiconductor band alignment plots from ionization potential (IP), electron affinity (EA), band gap (Eg), or valence/conduction band offsets (VBO/CBO). Use when drawing static band alignment figures for papers, slides, or reports, especially for heterojunctions, transport-layer stacks, and Type-I/II/III alignment comparisons. Not for solving spatial band bending, depletion width, electric field, or device electrostatics.
---

# Band Align Plot

Generate clean, publication-ready band alignment figures using static energy-level inputs.

## Scope

This skill is for:
- static vacuum-level band alignment plots
- relative band-offset plots
- multi-material side-by-side comparison figures
- device stack energy diagrams for papers and presentations

This skill is not for:
- solving Poisson equation
- calculating depletion width or built-in field
- predicting interface reconstruction or DFT-level offsets

## Default workflow

1. Determine whether the user wants:
   - vacuum-aligned plot using IP / EA / Eg, or
   - offset-based plot using VBO / CBO.
2. Normalize material names and check that required inputs are present.
3. If inputs are incomplete, state exactly what is missing.
4. Build a bapt config from structured inputs.
5. Render the figure through `scripts/render_band_align.py`.
6. Export at least one reusable config and one figure output.
7. Briefly explain what the figure shows and any assumptions used.

## Bundled resources

- `scripts/build_config.py`: input validation + payload-to-bapt config adapter
- `scripts/render_band_align.py`: main renderer and bapt CLI bridge
- `scripts/install_bapt.py`: workspace-local bapt installer and verifier
- `references/input-schema.md`: accepted input schema

## Escalation rules

If the user asks for:
- built-in potential
- depletion width
- electric field profile
- spatial Ec(x)/Ev(x)

then use the `band-diagram-calc` skill instead.

If the user asks for:
- atomistic interface structure
- DFT-derived band offset
- interface-specific IP / EA validation

then use the `interface-band-offset` skill instead.
