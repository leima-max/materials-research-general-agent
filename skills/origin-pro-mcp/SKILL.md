---
name: origin-pro-mcp
description: Control OriginLab Origin Pro through an MCP server backed by Windows COM automation. Use when the user wants Origin worksheets, publication figures, curve fitting, LabTalk execution, or graph export from Origin Pro.
---

# Origin-Pro-MCP

MCP Server for controlling OriginLab Origin Pro via COM automation. Enables AI assistants to create worksheets, plot graphs, apply publication styling, and perform curve fitting — all reflected in Origin's GUI in real-time.

## Location

`~/.openclaw/workspace-epi-opto-mentor/skills/origin-pro-mcp/`

## Prerequisites

- **Windows** with **Origin Pro 2020+** installed and running
- **Python 3.10+** (Windows Python, not WSL)
- `pywin32`, `Pillow`, `mcp` dependencies (installed automatically)

## Installation

Installed as an editable Python package in the workspace:

```bash
cd ~/.openclaw/workspace-epi-opto-mentor/skills/origin-pro-mcp
pip install -e .
```

## Usage

Start Origin Pro first, then run the MCP server:

```bash
origin-pro-mcp
```

Or directly:

```bash
python server.py
```

## MCP Tools (23 total)

### Project Management
| Tool | Description |
|------|-------------|
| `new_project` | Create new empty Origin project |
| `save_project` | Save project to .opju file |
| `load_project` | Open existing .opj/.opju file |

### Data
| Tool | Description |
|------|-------------|
| `create_worksheet` | Create new workbook |
| `set_worksheet_data` | Write column data (JSON arrays) |
| `get_worksheet_data` | Read worksheet data as JSON |
| `import_csv_to_worksheet` | Import CSV/text file |
| `list_worksheets` | List all open workbooks and graphs |

### Graphing
| Tool | Description |
|------|-------------|
| `create_graph` | Create graph (scatter, line, line+symbol, bar, etc.) |
| `add_plot_to_graph` | Add another dataset to existing graph |
| `set_axis_labels` | Set X/Y axis labels and title |
| `set_axis_range` | Set axis min/max values |
| `export_graph` | Export graph to PNG/JPG/PDF/SVG image with file verification |
| `export_all_graphs` | Export every graph in the project |

### Styling
| Tool | Description |
|------|-------------|
| `apply_publication_style` | **One-call publication formatting** (recommended) |
| `set_plot_style` | Set color, symbol, line width per plot |
| `set_graph_font` | Set font family and size |
| `set_legend` | Configure legend text and position |
| `set_tick_style` | Set tick direction and length |

### Analysis
| Tool | Description |
|------|-------------|
| `curve_fit` | Curve fitting with R², SSR statistics |
| `list_fitting_functions` | Show available fit functions |

### Advanced
| Tool | Description |
|------|-------------|
| `run_labtalk` | Execute any LabTalk script directly |
| `get_labtalk_variable` | Read a LabTalk variable value |

## Supported Plot Types

scatter, line, line+symbol, column, bar, area, histogram, box, contour, pie, bubble, 3d_scatter, 3d_surface

## Color Palette (Colorblind-Safe)

1. Blue → 2. Red → 3. Green → 4. Orange → 5. Purple → 6. Cyan

> Never use red + green as the only two colors.

## Publication Figure Workflow

See `skills/publication-figure.md` for detailed journal-ready figure creation workflow, including:
- Font size guide (Arial, 24pt titles, 20pt ticks, 18pt legend)
- Verified Origin COM quirks and workarounds
- Pre-export checklist
- Common figure recipes (scatter+fit, multi-dataset, bar chart, before/after)

## Architecture

```
AI Client (stdio MCP protocol)
    ↓
origin-pro-mcp (Windows Python + win32com)
    ↓
Origin Pro (GUI visible in real-time)
```

## License

MIT (from youngminsw/Origin-Pro-MCP)

## Source

https://github.com/youngminsw/Origin-Pro-MCP
