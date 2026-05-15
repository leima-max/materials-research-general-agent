# Minimal Examples - interface-band-offset

These examples are topic-neutral. The schema uses `material_a` and `material_b` only as side labels:

- `material_a` = configured side A material or component
- `material_b` = configured side B material or component

Use the smallest example that matches your current data completeness.

## 1) slab_only

File: `example-slab-based-minimal.json`

Use when you only have two slab calculations and want vacuum alignment, slab-based IP/EA, VBO/CBO, or heterojunction classification.

Required directories:

- `material_a.slab_dir`
- `material_b.slab_dir`

## 1b) slab_vasp_closed_loop

File: `example-slab-based-vasp-closed-loop-minimal.json`

Use when you want to generate matched slab surfaces, prepare two VASP surface jobs, and rerun the adapter later to collect `OUTCAR`, `vasprun.xml`, and `LOCPOT`.

## 2) explicit_only

File: `example-explicit-interface-minimal.json`

Use when you already have a finished explicit interface calculation and want interface potential lineup and explicit-interface VBO/CBO from bulk plus interface outputs.

Required directories:

- `material_a.bulk_dir`
- `material_b.bulk_dir`
- `interface.output_dir`

## 3) slab_plus_explicit

File: `example-slab-plus-explicit-minimal.json`

Use when you want the full chain: slab vacuum alignment for both sides, explicit interface potential lineup, and a combined structure-aware evidence chain.

Required directories:

- `material_a.bulk_dir`
- `material_a.slab_dir`
- `material_b.bulk_dir`
- `material_b.slab_dir`
- `interface.output_dir`

## 4) explicit_with_calculator

File: `example-explicit-interface-with-calculator-minimal.json`

Use when you want to generate the explicit interface model, route it through an `intermat` calculator method, and get adhesion-energy style output when the selected backend supports it.

## 5) explicit_vasp_closed_loop

File: `example-explicit-interface-vasp-closed-loop-minimal.json`

Use when you want to generate explicit-interface candidates, prepare surface/interface VASP jobs, and rerun the same adapter later to collect converged outputs.

## Configuration Notes

- Replace all `<CONFIGURE_PROJECT_PATH>/...` paths with real calculation directories.
- Replace `<CONFIGURE_SIDE_A_MATERIAL>` and `<CONFIGURE_SIDE_B_MATERIAL>` with the user's own material or component names.
- Default filenames are `OUTCAR`, `LOCPOT`, and `vasprun.xml`; override them through `directory_bundle.defaults` when needed.
- Heavy routes such as `vasp`, `qe`, `tb3`, `lammps`, `gpaw`, and `alignn_ff` need their own local executables or Python packages.
