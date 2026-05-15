# PROJECT_VARIABLES.md - Configure Before Use

This package is intentionally generic. Fill these variables with the installing user's own research context before expecting topic-specific analysis, simulation, literature strategy, or plotting defaults.

## Required Variables

| Variable | Value |
| --- | --- |
| `PROJECT_TITLE` | `<UNCONFIGURED>` |
| `RESEARCH_FIELD` | `<UNCONFIGURED>` |
| `MATERIAL_SYSTEM` | `<UNCONFIGURED>` |
| `DEVICE_OR_SAMPLE_STRUCTURE` | `<UNCONFIGURED>` |
| `PRIMARY_OBJECTIVES` | `<UNCONFIGURED>` |
| `KEY_CHARACTERIZATION_METHODS` | `<UNCONFIGURED>` |
| `KEY_DATA_TYPES` | `<UNCONFIGURED>` |
| `SIMULATION_SCOPE` | `<UNCONFIGURED>` |
| `DEFAULT_SOFTWARE_ENVIRONMENT` | `<UNCONFIGURED>` |
| `OUTPUT_STYLE` | `<UNCONFIGURED>` |
| `VALIDATION_CRITERIA` | `<UNCONFIGURED>` |

## Optional Variables

| Variable | Value |
| --- | --- |
| `LITERATURE_SCOPE` | `<UNCONFIGURED>` |
| `TARGET_JOURNAL_OR_REPORT_STYLE` | `<UNCONFIGURED>` |
| `KNOWN_BASELINE_RESULTS` | `<UNCONFIGURED>` |
| `KNOWN_FAILURE_MODES` | `<UNCONFIGURED>` |
| `DATA_NAMING_CONVENTION` | `<UNCONFIGURED>` |
| `PREFERRED_PLOTTING_STYLE` | `<UNCONFIGURED>` |
| `LOCAL_SOFTWARE_PATHS` | `<UNCONFIGURED>` |

## Use Rule

If any variable required for a task remains `<UNCONFIGURED>`, ask the user to supply it. Do not infer a research topic, material stack, sample structure, or benchmark result from this package.
