---
name: band-diagram-calc
description: Calculate 1D equilibrium semiconductor band diagrams for multilayer planar structures using material parameters such as electron affinity, band gap, dielectric constant, doping, thickness, and temperature. Use when the task involves built-in potential, depletion width, band bending, electric field, equilibrium Ec/Ev/Ef profiles, or interpreting junction physics in planar heterostructures. Not for atomistic interface construction or publication-only static alignment drawings.
---

# Band Diagram Calc

Calculate equilibrium 1D band bending and electrostatics for planar multilayer semiconductor stacks.

## Scope

This skill is for:
- equilibrium band diagrams
- built-in potential estimation
- depletion width analysis
- electric field profile extraction
- interpreting planar heterojunction physics

This skill is not for:
- DFT interface modeling
- atomistic slab/interface generation
- publication-only schematic drawing without electrostatic calculation
- full non-equilibrium device simulation or full TCAD replacement

## Default workflow

1. Identify the layer stack and preserve the physical order.
2. Collect required parameters for each layer.
3. Resolve each layer either from a known preset or from explicit effective-density-of-states parameters.
4. Run `scripts/solve_band_diagram.py`.
5. Export plots and numeric profiles.
6. Interpret the output in semiconductor-physics terms.

## Bundled resources

- `scripts/install_eq_band_diagram.py`: workspace-local installer and verifier for eq_band_diagram
- `scripts/solve_band_diagram.py`: main adapter and solver bridge
- `references/input-schema.md`: accepted input schema and backend-specific requirements
- `assets/presets/materials.json`: minimal preset material database for the eq_band_diagram backend

## Backend note

The `eq_band_diagram` backend needs more than Eg / EA / epsilon / doping. For non-preset materials it also needs effective density of states information (`nc_cm3`, `nv_cm3`) so it can construct the backend material model. If those values are missing, fail explicitly instead of inventing them.

## Escalation rules

If the user only wants a clean static figure, use `band-align-plot`.

If the user needs:
- atomistic interface structure
- interface-specific DFT offsets
- slab/vacuum calculations
- first-principles validation of Anderson-rule assumptions

use `interface-band-offset`.
