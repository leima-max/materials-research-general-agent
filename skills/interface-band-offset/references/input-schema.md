# Input Schema - interface-band-offset

This file defines the accepted input structure for the `interface-band-offset` skill.

## Top-level schema

```json
{
  "task": "analyze interface band offset",
  "mode": "quick_estimate | slab_based | explicit_interface",
  "inputs": {},
  "options": {}
}
```

For `slab_based`, the adapter now supports a `surf_andersen`-like route driven by local VASP slab outputs (`LOCPOT`, `OUTCAR`, `vasprun.xml`).

## Mode overview

### `quick_estimate`
Use when explicit interface structure is not yet available.

Accepted inputs:
- `material_a.name`
- `material_b.name`
- optional `reference_values.ip`
- optional `reference_values.ea`
- optional `reference_values.band_offsets`

### `slab_based`
Use when slab-derived values or per-surface reference values are available.

Accepted inputs:
- all `quick_estimate` fields
- optional `material_a.structure_source`
- optional `material_b.structure_source`
- optional `material_a.surface`
- optional `material_b.surface`
- optional `material_a.termination`
- optional `material_b.termination`
- optional `material_a.slab_output_dir`
- optional `material_b.slab_output_dir`
- optional explicit `locpot_path`, `outcar_path`, `vasprun_path` for each material
- optional `vacuum_axis` for each material (`X`, `Y`, or `Z`; defaults to `X` to match the current upstream intermat slab parser behavior)
- optional `inputs.calculator` when `method = "vasp"`

Behavior:
- if both materials provide slab outputs, the adapter uses a `surf_andersen`-like vacuum-alignment path
- if `inputs.calculator.method = "vasp"` and both materials provide `jid` or `structure_source`, the adapter prepares matched surface-slab VASP jobs and later auto-collects slab outputs from those prepared folders
- otherwise, it falls back to `reference_values`

### `explicit_interface`
Use when an explicit interface model is requested, or when an already-finished interface `LOCPOT` should be used to extract an interface-specific potential lineup `ΔV`.

Accepted inputs:
- all `slab_based` fields
- optional `matching.max_lattice_mismatch_percent`
- optional `matching.supercell_search`
- optional `calculation_context.method_level`
- optional `calculation_context.vacuum_thickness_ang`
- optional `calculation_context.slab_thickness_ang`
- optional `inputs.interface_outputs.output_dir`
- optional `inputs.interface_outputs.locpot_path`
- optional `inputs.interface_outputs.outcar_path`
- optional `inputs.interface_outputs.vasprun_path`
- optional `inputs.interface_outputs.vacuum_axis`
- optional `inputs.interface_outputs.left_index`
- optional `inputs.interface_outputs.peak_width`
- optional `inputs.interface_outputs.polar`
- optional `inputs.directory_bundle`
- optional `inputs.calculator`
- optional `material_a.bulk_outcar_path`
- optional `material_b.bulk_outcar_path`
- optional `reference_values.bulk_band_edges`

Behavior:
- if `interface_outputs` is supplied, the adapter extracts `ΔV` from the interface `LOCPOT`
- if bulk VBM/CBM references are also supplied, it derives explicit-interface `VBO/CBO`
- if structure routes are supplied too, the adapter can also generate/export the explicit interface model in the same run
- if `inputs.calculator` is supplied with structure routes, the adapter forwards the calculator path into `intermat.calculate_wad(...)`, captures run artifacts, and returns adhesion-energy summaries when upstream intermat provides them
- if `inputs.calculator.method = "vasp"`, the adapter switches to a dedicated closed-loop path: it prepares per-candidate VASP input directories for film-surface / substrate-surface / interface jobs, then auto-collects slab alignment plus explicit-interface `ΔV` once completed `OUTCAR/vasprun.xml/LOCPOT` files are present
- if `directory_bundle` is supplied, the adapter expands bulk/slab/interface directories into explicit file paths before validation

## Core note for the current backend

The current intermat adapter supports these verified paths:
1. reference-driven quick estimate / Anderson-style offset synthesis
2. slab-based `surf_andersen`-like vacuum alignment from local `LOCPOT` / `OUTCAR` / `vasprun.xml`
3. explicit-interface `LOCPOT ΔV` extraction from a finished interface calculation
4. lightweight interface summary and downstream parameter packaging
5. explicit interface generation through `intermat.run_intermat.main(...)` using JARVIS `jid` or local structure files
6. deeper calculator routing for `ewald`, `emt`, `alignn_ff`, `matgl`, `eam_ase`, `vasp`, `qe`, `lammps`, `gpaw`, and `tb3` with preflight checks before execution

It does **not** claim to run heavy external calculator jobs unless that path is explicitly implemented and verified.

## Standard fields

### `inputs.material_a` and `inputs.material_b`
Accepted fields:
- `name` (required)
- `jid` (optional, JARVIS material id such as `JVASP-1002`)
- `structure_source`
- `surface`
- `termination`
- `slab_output_dir`
- `locpot_path`
- `outcar_path`
- `vasprun_path`
- `vacuum_axis`
- `notes`

### `inputs.reference_values`
Accepted fields:
- `ip`: object keyed by material name
- `ea`: object keyed by material name
- `band_offsets`: object with `vbo_ev` and/or `cbo_ev`
- `bulk_band_edges`: object keyed by material name, each containing `vbm` and `cbm`
- `sources`: list of strings

### `inputs.matching`
Accepted fields:
- `max_lattice_mismatch_percent`
- `supercell_search`
- `prefer_low_strain`

### `inputs.calculation_context`
Accepted fields:
- `method_level`
- `vacuum_thickness_ang`
- `slab_thickness_ang`
- `perform_relaxation`
- `disp_intvl`
- `separation_ang`
- `rotate_xz`
- `dataset`
- `queue`
- `walltime`
- `extra_lines`
- `from_conventional_structure_film`
- `from_conventional_structure_subs`
- `verbose`

### `inputs.calculator`
Use this when the explicit-interface run should go beyond structure generation and actually call an `intermat` calculator route.

Accepted fields:
- `method` (`ewald`, `emt`, `alignn_ff`, `matgl`, `eam_ase`, `vasp`, `qe`, `lammps`, `gpaw`, `tb3`)
- `do_surfaces`
- `plot_wads`
- `kp_length`
- `sub_job`
- `queue`
- `walltime`
- `extra_lines`
- `copy_files`
- `potential`
- `vasp` (object: `vasp_cmd`, `inc`, and related VASP settings)
- `qe` (object: `qe_cmd`, `qe_params`)
- `lammps` (object: `lammps_cmd`, `pair_style`, `pair_coeff`, `atom_style`, `control_file`)
- `gpaw` (object: `cutoff`, `xc`, `basis`, `spinpol`, `nbands`, `convergence`, `out_file`, `kp_length`, etc.)
- `tb3_lines` (list of Julia script lines to override upstream defaults)

Behavior:
- calculator routes are valid with `mode = "explicit_interface"`, and `mode = "slab_based"` is additionally supported for `method = "vasp"`
- preparation routes require both materials to provide `jid` or `structure_source`
- the adapter runs a preflight check first and fails clearly when required modules/commands are missing
- `do_surfaces=false` is allowed but upstream intermat leaves `wads` as placeholder values in that case, so adhesion-energy ranking is not meaningful

Special notes for `method = "vasp"`:
- accepted `vasp.run_mode`: `auto`, `prepare_only`, `collect_only`
- `prepare_only`: write candidate-specific VASP input folders and a manifest, but do not expect outputs yet
- `collect_only`: do not rely on new preparation work; scan the prepared candidate folders for finished `OUTCAR/vasprun.xml/LOCPOT` and, if present, derive slab alignment + explicit-interface `ΔV`
- prepared folders contain `POSCAR`, `INCAR`, `KPOINTS`, `run_vasp.sh`, `job.py`, and `job_metadata.json`
- the current VASP closed-loop implementation deliberately avoids requiring local POTCAR generation during preparation, so preparation can be done off-cluster and execution can happen later on the VASP environment

Additional notes for `slab_based + method = "vasp"`:
- the adapter prepares only two matched surface jobs: `material_a_surface` and `material_b_surface`
- surface preparation ignores interface displacement scans because the surf_andersen-like route only needs the two slab surfaces
- collection succeeds after both prepared surface folders contain converged `OUTCAR`, `vasprun.xml`, and `LOCPOT`

### `inputs.interface_outputs`
Accepted fields:
- `output_dir`
- `locpot_path`
- `outcar_path`
- `vasprun_path`
- `vacuum_axis`
- `left_index`
- `peak_width`
- `polar`

### `inputs.directory_bundle`
Use this when the real calculation results are already organized as bulk/slab/interface directories and you want one compact payload instead of repeating individual file paths.

Accepted fields:
- `defaults.bulk_outcar_name`
- `defaults.slab_locpot_name`
- `defaults.slab_outcar_name`
- `defaults.slab_vasprun_name`
- `defaults.interface_locpot_name`
- `defaults.interface_outcar_name`
- `defaults.interface_vasprun_name`
- `material_a.bulk_dir`
- `material_a.slab_dir`
- `material_a.vacuum_axis`
- `material_b.bulk_dir`
- `material_b.slab_dir`
- `material_b.vacuum_axis`
- `interface.output_dir` or `interface.interface_dir`
- `interface.vacuum_axis`
- `interface.left_index`
- `interface.peak_width`
- `interface.polar`

Expansion rules:
- `material_*.bulk_dir` -> `material_*.bulk_outcar_path`
- `material_*.slab_dir` -> `material_*.slab_output_dir` plus `locpot_path/outcar_path/vasprun_path`
- `interface.output_dir` -> `inputs.interface_outputs.output_dir` plus `locpot_path/outcar_path/vasprun_path`

Example templates:
- `references/bulk-slab-interface-template.json`
- `references/example-slab-based-minimal.json`
- `references/example-slab-based-vasp-closed-loop-minimal.json`
- `references/example-explicit-interface-minimal.json`
- `references/example-slab-plus-explicit-minimal.json`
- `references/minimal-examples.md`

### `options`
Accepted fields:
- `export_structure_files`
- `compare_methods`
- `output_format`
- `emit_downstream_parameters`

`options.compare_methods` is currently treated as a lightweight alias source for picking a calculator method when `inputs.calculator.method` is omitted; the adapter does not yet execute a full multi-method batch in one call.

## Boundary rules

This schema does not focus on:
- depletion width
- built-in electric field
- 1D Ec(x)/Ev(x)
- publication figure styling

Those belong to other skills.
