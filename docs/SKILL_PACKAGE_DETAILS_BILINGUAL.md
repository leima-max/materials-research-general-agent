# 技能包详情 / Skill Package Details

本文档给出材料科研通用 Agent 的技能边界、典型输入、典型输出和使用注意事项。

This document describes the scope, typical inputs, typical outputs, and usage notes for the Materials Research General Agent skill package.

## 1. 文献与知识工作 / Literature And Knowledge Work

### `literature-search`

中文：用于检索论文、梳理相关工作、生成关键词组合、建立初始引用列表。适合课题开题、审稿回复、综述框架和方向调研。

English: Use for paper discovery, related-work mapping, keyword expansion, and initial citation lists. Suitable for proposal preparation, reviewer responses, review outlines, and field exploration.

Typical outputs:

- keyword strategy
- citation list
- topic map
- paper screening table

### `zotero-literature-review`

中文：用于 Zotero 文献库中的元数据核查、PDF/笔记/注释辅助综述、引用安全写作和可追溯文献总结。

English: Use for Zotero library metadata checks, PDF/note/annotation-assisted reviews, citation-safe writing, and traceable literature synthesis.

Typical outputs:

- verified bibliography
- structured literature review
- collection-level summary
- citation-safe notes

## 2. 数据处理与科研绘图 / Data Processing And Scientific Plotting

### `pythesis-plot`

中文：用于论文图、学位论文图、对比图、拟合图和可复现 Python 绘图流程。

English: Use for thesis figures, paper figures, comparison plots, fitting plots, and reproducible Python plotting workflows.

### `origin-pro-mcp`

中文：通过 MCP 调用 Origin Pro，实现工作表创建、数据导入、曲线拟合、出版级样式设置、LabTalk 执行和图片导出。

English: Control Origin Pro through MCP for worksheet creation, data import, curve fitting, publication styling, LabTalk execution, and graph export.

Prerequisites:

- Windows
- Origin Pro 2020+
- Windows Python 3.10+
- `mcp`, `pywin32`, `Pillow`

Setup:

```powershell
.\setup-origin-pro-mcp.ps1
```

## 3. 结构表征 / Structural Characterization

### `xrd-pyfai`

中文：用于 2D XRD、GIWAXS、WAXS 探测器图像到 1D 曲线、cake 图、方位角分布和织构证据链的预处理。

English: Use for 2D XRD, GIWAXS, and WAXS detector images, including 1D integration, cake remapping, azimuthal profiles, and texture evidence.

Typical inputs:

- detector image
- `.poni` calibration
- mask, dark, or flat correction files when available

Typical outputs:

- integrated CSV
- processed image
- diagnostic plots
- reproducible config

## 4. 能带与界面 / Band And Interface Analysis

### `band-align-plot`

中文：用于静态能带排列图，适合论文、PPT 和报告中的 Type-I/II/III 异质结示意。

English: Use for static band alignment figures, especially Type-I/II/III heterojunction diagrams for papers, slides, and reports.

### `band-diagram-calc`

中文：用于一维平衡能带弯曲、内建电势、耗尽宽度、电场和多层半导体结分析。

English: Use for 1D equilibrium band bending, built-in potential, depletion width, electric field, and multilayer semiconductor junction analysis.

### `interface-band-offset`

中文：用于考虑具体界面取向和结构的能带偏移分析，适合 Anderson 规则不足以解释界面现象时使用。

English: Use for orientation-aware and atomistic interface band-offset analysis when simple Anderson-rule estimates are insufficient.

## 5. 光电器件与仿真 / Optoelectronic Devices And Simulation

### `photodetector-pyradi`

中文：用于光探测器光谱响应、QE、R、NEP、D*、噪声模型和暗电流假设下的指标提取。

English: Use for photodetector spectral response, QE, responsivity, NEP, D*, noise models, and dark-current-based metric extraction.

Required context:

- active area
- bias
- wavelength or spectrum
- noise bandwidth or noise model
- measurement conditions

### `comsol-opto-simulation`

中文：用于 COMSOL 光学/光电仿真配置、薄膜异质结模板、参数扫描和结果提取。使用时目标电脑必须安装并授权 COMSOL。

English: Use for COMSOL optical/optoelectronic simulation setup, thin-film heterojunction templates, parameter sweeps, and result extraction. COMSOL must be installed and licensed on the target machine.

## 6. 文本与科研流程 / Writing And Research Workflow

### `humanizer-1.0.0`

中文：用于中英文科研文本润色，使表达更自然、清晰、像真实研究者写作。

English: Use to polish Chinese or English research text for clarity, naturalness, and human-authored style.

### `scientify`

中文：用于科研流程辅助、想法生成、文献调研和工作区管理。

English: Use for research-pipeline assistance, idea generation, literature surveys, and workspace management.

## 推荐使用顺序 / Recommended Order

中文：

1. 先配置 `PROJECT_VARIABLES.md`。
2. 数据任务先读取原始数据。
3. 根据任务选择对应技能。
4. 输出图、表、脚本和结论。
5. 运行验证脚本或最小复现实验。

English:

1. Configure `PROJECT_VARIABLES.md` first.
2. For data tasks, read raw data first.
3. Select the matching skill.
4. Produce figures, tables, scripts, and conclusions.
5. Run verification scripts or minimal reproduction checks.
