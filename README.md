# 材料科研通用 Agent / Materials Research General Agent

面向 Codex 项目的材料科研通用 Agent 技能包，覆盖科研问题拆解、文献综述、数据处理、科研绘图、衍射分析、能带分析、光电探测器指标提取、COMSOL 仿真辅助、Origin Pro 自动绘图和 Zotero 本地文献工作流。

This is a portable Codex project package for materials-science research agents. It covers research planning, literature review, data analysis, publication plotting, diffraction processing, band analysis, photodetector metrics, COMSOL-assisted simulation, Origin Pro automation, and local Zotero workflows.

## 目录 / Contents

- [快速安装 / Quick Install](#快速安装--quick-install)
- [技能包详情 / Skill Package Details](#技能包详情--skill-package-details)
- [MCP 支持 / MCP Support](#mcp-支持--mcp-support)
- [使用方法 / Usage](#使用方法--usage)
- [工作规范 / Working Rules](#工作规范--working-rules)
- [验证 / Verification](#验证--verification)
- [仓库结构 / Repository Layout](#仓库结构--repository-layout)

## 快速安装 / Quick Install

### 中文

1. 下载或克隆本仓库。
2. 在 PowerShell 中进入仓库目录。
3. 将本包安装到你的 Codex 项目目录：

```powershell
.\install.ps1 -TargetProject "D:\your-codex-project"
```

4. 进入目标项目，按自己的课题填写：

```text
PROJECT_VARIABLES.md
DEVICE_CONFIG.md
```

5. 验证安装：

```powershell
.\verify-package.ps1 -Root "D:\your-codex-project"
```

### English

1. Download or clone this repository.
2. Open PowerShell in the repository root.
3. Install the package into your Codex project:

```powershell
.\install.ps1 -TargetProject "D:\your-codex-project"
```

4. Open the target project and fill in your own research context:

```text
PROJECT_VARIABLES.md
DEVICE_CONFIG.md
```

5. Verify the installation:

```powershell
.\verify-package.ps1 -Root "D:\your-codex-project"
```

## 技能包详情 / Skill Package Details

| Skill | 中文说明 | English Description |
| --- | --- | --- |
| `literature-search` | 多平台文献检索、相关工作梳理、关键词扩展和引用列表整理。 | Academic literature search, related-work mapping, keyword expansion, and citation-list preparation. |
| `zotero-literature-review` | 基于 Zotero 的文献综述、元数据校验、PDF/笔记/注释辅助整理。 | Zotero-based literature review, metadata auditing, and PDF/note/annotation-assisted synthesis. |
| `xrd-pyfai` | 2D XRD、GIWAXS、WAXS 图像积分、极图/方位角分析和可复现预处理。 | 2D XRD, GIWAXS, and WAXS image integration, cake remapping, azimuthal profiling, and reproducible preprocessing. |
| `pythesis-plot` | 论文和学位论文风格的 Python 科研绘图与数据可视化流程。 | Thesis-style and publication-oriented Python scientific plotting workflows. |
| `band-align-plot` | 根据 IP、EA、Eg、VBO/CBO 绘制半导体能带对齐图。 | Publication-ready semiconductor band alignment plots from IP, EA, Eg, VBO, and CBO. |
| `band-diagram-calc` | 多层平面半导体结构的一维平衡能带、内建势、电场和耗尽区估算。 | 1D equilibrium band diagrams, built-in potential, field, and depletion estimates for multilayer planar semiconductors. |
| `interface-band-offset` | 面向界面取向、原子结构和 DFT/ML 辅助分析的界面能带偏移工作流。 | Interface-aware band-offset workflows using orientation, atomistic structures, and DFT/ML-assisted analysis. |
| `photodetector-pyradi` | 从光谱响应、QE、噪声和暗电流数据提取 R、NEP、D* 等光探测指标。 | Photodetector metric extraction for responsivity, QE, NEP, D*, and noise/dark-current assumptions. |
| `comsol-opto-simulation` | 薄膜异质结、光学/光电耦合和参数扫描的 COMSOL 辅助脚本与模板。 | COMSOL helper scripts and templates for thin-film heterojunction optical/optoelectronic simulation and parameter sweeps. |
| `origin-pro-mcp` | 通过 MCP 和 Windows COM 控制 Origin Pro，自动建表、绘图、拟合、出版级样式和导出。 | MCP server for Origin Pro via Windows COM: worksheets, plots, fitting, publication styling, LabTalk, and export. |
| `humanizer-1.0.0` | 中英文科研文本润色，降低机械感并改善可读性。 | Scientific text polishing to improve naturalness, clarity, and readability. |
| `scientify` | 科研流程、想法生成、文献调研和工作区管理辅助。 | Research-pipeline, idea-generation, literature-survey, and workspace-management helpers. |

## MCP 支持 / MCP Support

### Origin Pro MCP

中文：

- 需要 Windows、Origin Pro 2020+、Windows Python 3.10+。
- 使用前先启动 Origin Pro。
- 安装并生成路径正确的 MCP 配置：

```powershell
.\setup-origin-pro-mcp.ps1
```

如果 Python 不在 `PATH`：

```powershell
.\setup-origin-pro-mcp.ps1 -Python "C:\Path\To\python.exe"
```

English:

- Requires Windows, Origin Pro 2020+, and Windows Python 3.10+.
- Start Origin Pro before using the MCP server.
- Install dependencies and generate a path-correct MCP config:

```powershell
.\setup-origin-pro-mcp.ps1
```

If Python is not on `PATH`:

```powershell
.\setup-origin-pro-mcp.ps1 -Python "C:\Path\To\python.exe"
```

### Zotero MCP

中文：

- 需要本地 Zotero 和可访问的 Zotero 数据库。
- 运行：

```powershell
.\setup-zotero-mcp.ps1
```

English:

- Requires local Zotero and access to a Zotero database.
- Run:

```powershell
.\setup-zotero-mcp.ps1
```

## 使用方法 / Usage

### 中文

安装到 Codex 项目后，直接围绕研究任务提问，例如：

```text
请根据这组 I-V 数据计算整流比、暗电流和正偏工作区性能。
请把这张 GIWAXS 图积分成 1D 曲线并分析取向。
请用 Origin Pro 生成一张符合期刊风格的散点+拟合图。
请帮我围绕某材料体系做近五年文献综述。
请规划一个 COMSOL 薄膜异质结光吸收仿真。
```

使用前建议先配置 `PROJECT_VARIABLES.md`，至少写清研究领域、材料体系、样品/器件结构、表征方法、数据类型和验证标准。未配置时，Agent 应先询问关键信息，不能替用户假设具体课题。

### English

After installing into a Codex project, ask research tasks directly, for example:

```text
Calculate rectification ratio, dark current, and operating-region metrics from this I-V dataset.
Integrate this GIWAXS image into a 1D curve and analyze orientation.
Use Origin Pro to create a journal-style scatter plot with fitting.
Prepare a five-year literature review for this material system.
Plan a COMSOL optical absorption simulation for a thin-film heterojunction.
```

Before use, configure `PROJECT_VARIABLES.md` with your research field, material system, sample/device structure, characterization methods, data types, and validation criteria. If these are missing, the Agent should ask rather than invent project-specific assumptions.

## 工作规范 / Working Rules

### 中文

- 先读原始数据，再做清洗、拟合、绘图和结论。
- 所有定量结论必须写明单位、公式、测试条件和假设。
- 修改文件、脚本或配置后必须运行验证。
- 实验建议必须包含目标、操作步骤、预期结果、失败判据和下一步。
- 结构表征结论要连接到性能指标或机制，不只描述形貌。
- 涉及外部动作、生产配置、删除或不可逆操作时先确认。
- 使用技能时先阅读对应 `skills/<skill>/SKILL.md`。

### English

- Read raw data first, then clean, fit, plot, and conclude.
- Quantitative conclusions must state units, formulas, test conditions, and assumptions.
- Verify after changing files, scripts, or configuration.
- Experimental suggestions should include goal, steps, expected result, failure criterion, and next step.
- Structural characterization should be connected to performance metrics or mechanism, not morphology alone.
- Confirm before external actions, production changes, deletion, or irreversible operations.
- Read `skills/<skill>/SKILL.md` before using a bundled skill.

## 验证 / Verification

验证包本身：

```powershell
.\verify-package.ps1
```

验证目标项目：

```powershell
.\verify-package.ps1 -Root "D:\your-codex-project"
```

Expected result:

- required project files exist
- 12 skill directories are discoverable
- `config/`, `docs/`, `examples/`, `mcp/`, `plugins/`, `scripts/`, and `skills/` exist
- Origin Pro and Zotero setup scripts are present

## 仓库结构 / Repository Layout

```text
.
├── AGENTS.md
├── PROJECT_VARIABLES.md
├── DEVICE_CONFIG.md
├── README.md
├── README_INSTALL.md
├── install.ps1
├── verify-package.ps1
├── setup-origin-pro-mcp.ps1
├── setup-zotero-mcp.ps1
├── config/
├── docs/
├── examples/
├── mcp/
├── plugins/
├── scripts/
└── skills/
```

## 重要说明 / Important Notes

中文：

- 本包是通用材料科研 Agent 模板，不预设某个具体课题。
- COMSOL、Origin Pro、Zotero 等第三方软件需要用户在目标电脑自行安装并授权。
- 部分技能内含本地 vendor 依赖以增强离线可用性，因此仓库体积较大。

English:

- This package is a general materials-research Agent template and does not assume a specific research topic.
- COMSOL, Origin Pro, Zotero, and other third-party tools must be installed and licensed on the target machine by the user.
- Some skills bundle local vendor dependencies for offline portability, so the repository is large.
