---
name: interface-band-offset
description: Build and analyze atomistic material interfaces to estimate or validate ionization potential (IP), electron affinity (EA), work function, band offsets, and heterojunction type using structure-based workflows. Use when the task requires interface-specific band alignment beyond simple Anderson-rule estimates, including slab/interface construction, orientation-aware comparison, or DFT/ML-assisted interface property analysis. Not for simple publication plotting or 1D equilibrium electrostatic band bending alone.
---

# Interface Band Offset

Build and analyze atomistic interfaces for structure-aware band-offset and interface-property evaluation.

## Scope

This skill is for:
- atomistic slab and interface setup
- orientation-aware interface comparison
- extracting or validating IP / EA / work function
- estimating valence/conduction band offsets
- classifying heterojunction type
- checking whether simple vacuum-level alignment is reasonable for a specific interface

This skill is not for:
- publication-only plotting
- simple schematic energy diagrams
- 1D equilibrium Poisson-only band bending

## Default workflow

1. Determine the target pair of materials and the intended interface.
2. Collect structure sources or reference values.
3. Choose the analysis mode:
   - quick estimate
   - slab-based (`surf_andersen`-like route from local slab outputs, VASP slab closed-loop preparation/collection, or fallback reference values)
   - explicit interface (structure generation, explicit-interface `LOCPOT ΔV`, calculator-assisted adhesion-energy scan, or combinations of them)
4. Run `scripts/run_band_offset_analysis.py`.
5. Export interface-sensitive offsets and downstream parameters.

## Bundled resources

- `scripts/install_intermat.py`: workspace-local installer and verifier for intermat
- `scripts/run_band_offset_analysis.py`: main adapter and analysis bridge
- `references/input-schema.md`: accepted input schema and backend-specific requirements
- `references/bulk-slab-interface-template.json`: compact three-directory payload template for real bulk/slab/interface result layouts
- `references/example-slab-based-minimal.json`: minimal slab-only example
- `references/example-slab-based-vasp-closed-loop-minimal.json`: minimal slab-based VASP closed-loop preparation example
- `references/example-explicit-interface-minimal.json`: minimal explicit-interface example
- `references/example-slab-plus-explicit-minimal.json`: minimal hybrid slab+explicit example
- `references/example-explicit-interface-with-calculator-minimal.json`: minimal explicit-interface + calculator example
- `references/example-explicit-interface-vasp-closed-loop-minimal.json`: minimal VASP closed-loop preparation example
- `references/minimal-examples.md`: quick selector for which minimal example to start from

## Backend note

The current implementation supports four practical tiers:
- reference-driven quick estimate
- `surf_andersen`-like slab vacuum alignment from local `LOCPOT` / `OUTCAR` / `vasprun.xml`
- slab-based VASP closed-loop preparation/collection for matched surface slabs
- explicit-interface `LOCPOT ΔV` extraction from finished interface calculations
- explicit interface generation via `intermat.run_intermat.main(...)`
- deeper `intermat` calculator routing with preflight checks and artifact capture
- dedicated VASP closed-loop preparation/collection for surface + interface jobs

If the requested workflow needs heavy external calculators, preflight first and fail clearly instead of pretending the calculation ran.

For ase-based calculator methods (`emt`, `alignn_ff`, `matgl`, `eam_ase`, `gpaw`), make sure the local vendor environment has the needed Python packages first. The bundled installer can now be used to add optional extras before running the calculator route.

For `method = "vasp"`, prefer the dedicated closed-loop path in this skill rather than relying on upstream `intermat` job naming. It prepares unique per-candidate film-surface / substrate-surface / interface folders, writes a manifest, and reuses the same entry point to collect `LOCPOT`/`OUTCAR`/`vasprun.xml` later.

## Hand-off rules

If the user wants a final paper figure, use `band-align-plot`.

If the user wants depletion width, built-in field, or Ec(x)/Ev(x), use `band-diagram-calc`.
