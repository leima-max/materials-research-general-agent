# Input Schema - band-diagram-calc

This file defines the accepted input structure for the `band-diagram-calc` skill.

## Purpose

Use this skill to calculate 1D equilibrium semiconductor band diagrams for planar multilayer structures with the `eq_band_diagram` backend.

## Top-level schema

```json
{
  "task": "solve equilibrium band diagram",
  "mode": "full_profile | built_in_only | compare_structures",
  "inputs": {},
  "options": {}
}
```

## Core backend rule

The `eq_band_diagram` backend needs enough information to construct a material model.

Each layer must resolve through one of these routes:

### Route A: preset material
Provide:
- `material_key`

and let the adapter load the material parameters from `assets/presets/materials.json`.

### Route B: explicit material parameters
Provide all of:
- `ea`
- `eg`
- `epsilon_r`
- `nc_cm3`
- `nv_cm3`

The adapter maps these to the backend `Material(NC, NV, EG, chi, eps)` object.

Do not invent `nc_cm3` or `nv_cm3` if they are unknown.

## Standard `inputs.layers[]` fields

Each layer accepts:
- `name` (required)
- `material_key` (optional preset route)
- `thickness_nm` (required)
- `doping_type` (required: `n`, `p`, or `intrinsic`)
- `doping_cm3` (required, use `0` for intrinsic)
- `ea` (required for explicit route)
- `eg` (required for explicit route)
- `epsilon_r` (required for explicit route)
- `nc_cm3` (required for explicit route)
- `nv_cm3` (required for explicit route)
- `notes` (optional)

Example:

```json
{
  "name": "Si_p",
  "material_key": "Si",
  "thickness_nm": 350,
  "doping_type": "p",
  "doping_cm3": 1e16
}
```

or

```json
{
  "name": "custom_layer",
  "thickness_nm": 150,
  "doping_type": "n",
  "doping_cm3": 1e15,
  "ea": 4.05,
  "eg": 1.12,
  "epsilon_r": 11.9,
  "nc_cm3": 2.8e19,
  "nv_cm3": 2.65e19
}
```

## Other accepted `inputs` fields

- `temperature_k` (optional for the adapter, but current backend is fixed at ~300 K internally; if not 300 K, warn clearly)
- `contacts.left_boundary` (`neutral` or `fixed`, optional)
- `contacts.right_boundary` (`neutral` or `fixed`, optional)
- `boundary_conditions.evac_start` (optional numeric eV)
- `boundary_conditions.evac_end` (optional numeric eV)

## Accepted `options` fields

- `grid_points`
- `solver_tolerance`
- `max_iterations`
- `export_csv`
- `plot_format`
- `figure_dpi`
- `include_field_profile`
- `include_charge_profile`

## Boundary rules

This schema does not focus on:
- `surface`
- `termination`
- `structure_source`
- `vacuum_thickness_ang`
- publication-only style tuning

Those belong to other skills.
