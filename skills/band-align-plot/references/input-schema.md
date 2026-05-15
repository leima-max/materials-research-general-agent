# Input Schema - band-align-plot

This file defines the accepted input structure for the `band-align-plot` skill.

## Top-level schema

```json
{
  "task": "plot band alignment",
  "mode": "vacuum_alignment | offset_alignment | device_stack",
  "inputs": {},
  "options": {}
}
```

## Core rules

- `materials` is required in all modes.
- `vacuum_alignment` needs `ip` and `ea` for every material.
- `offset_alignment` needs `eg` for every material and adjacent `offsets` entries.
- `device_stack` preserves `stack_order` exactly as given.
- Energy units are eV.

## Accepted `materials[]` fields

- `name` (required)
- `ip`
- `ea`
- `eg`
- `label`
- `color`
- `vb_colour`
- `cb_colour`
- `fade`

## Accepted `offsets[]` fields

- `left` (required)
- `right` (required)
- `vbo` or `cbo` (at least one required)
- `source`

Offsets are interpreted as adjacent-interface deltas in the same order as the material stack.

## Accepted `options` fields

- `output_format`
- `style`
- `show_values`
- `show_axis`
- `dpi`
- `figure_width_inch`
- `figure_height_inch`
- `bar_width`
- `gap`
- `font`
- `font_size`
- `name_colour`
- `fade_cb`
- `gradients`
- `photocat`

## Boundary rules

This schema does not accept:
- `doping_type`
- `doping_cm3`
- `epsilon_r`
- `temperature_k`
- `surface`
- `termination`
- `vacuum_thickness_ang`
