# DEVICE_CONFIG.md - Generic Project Configuration Template

Use this file to configure the user's own research system before performing topic-specific analysis or simulation. Leave placeholders unset until the user provides real project details.

## Project Overview

| Variable | Value |
| --- | --- |
| `PROJECT_TITLE` | `<UNCONFIGURED>` |
| `RESEARCH_FIELD` | `<UNCONFIGURED>` |
| `PRIMARY_OBJECTIVES` | `<UNCONFIGURED>` |
| `TARGET_OUTPUTS` | `<UNCONFIGURED>` |

## Sample, Device, Or System Structure

For layered devices, samples, cells, reactors, components, or multi-domain simulations, configure the stack or structure here.

| Component / Layer / Domain | Role | Geometry / Thickness / Size | Preparation / Source | Key Parameters |
| --- | --- | --- | --- | --- |
| `<COMPONENT_1>` | `<UNCONFIGURED>` | `<UNCONFIGURED>` | `<UNCONFIGURED>` | `<UNCONFIGURED>` |
| `<COMPONENT_2>` | `<UNCONFIGURED>` | `<UNCONFIGURED>` | `<UNCONFIGURED>` | `<UNCONFIGURED>` |
| `<COMPONENT_3>` | `<UNCONFIGURED>` | `<UNCONFIGURED>` | `<UNCONFIGURED>` | `<UNCONFIGURED>` |

## Material Or System Parameters

| Parameter | Symbol | Value | Unit | Source / Confidence |
| --- | --- | --- | --- | --- |
| `<PARAMETER_1>` | `<SYMBOL>` | `<UNCONFIGURED>` | `<UNIT>` | `<MEASURED / LITERATURE / ASSUMED>` |
| `<PARAMETER_2>` | `<SYMBOL>` | `<UNCONFIGURED>` | `<UNIT>` | `<MEASURED / LITERATURE / ASSUMED>` |
| `<PARAMETER_3>` | `<SYMBOL>` | `<UNCONFIGURED>` | `<UNIT>` | `<MEASURED / LITERATURE / ASSUMED>` |

## Characterization And Data

| Category | Configured Values |
| --- | --- |
| Key characterization methods | `<UNCONFIGURED>` |
| Key raw data formats | `<UNCONFIGURED>` |
| Required measurement conditions | `<UNCONFIGURED>` |
| Calibration / baseline requirements | `<UNCONFIGURED>` |
| Uncertainty or repeatability requirements | `<UNCONFIGURED>` |

## Simulation Configuration

| Variable | Value |
| --- | --- |
| `SIMULATION_SCOPE` | `<UNCONFIGURED>` |
| `PHYSICS_MODULES` | `<UNCONFIGURED>` |
| `GEOMETRY_DIMENSION` | `<UNCONFIGURED>` |
| `BOUNDARY_CONDITIONS` | `<UNCONFIGURED>` |
| `INITIAL_CONDITIONS` | `<UNCONFIGURED>` |
| `SOLVER_STRATEGY` | `<UNCONFIGURED>` |
| `PARAMETER_SWEEP_PLAN` | `<UNCONFIGURED>` |
| `VALIDATION_CRITERIA` | `<UNCONFIGURED>` |

## Reporting Requirements

- State all user-provided assumptions.
- Mark unconfigured variables clearly.
- Report formulas, fitting models, software versions, and scripts used.
- Attach editable outputs when practical.
- Do not treat placeholder values as real experimental or simulation parameters.
