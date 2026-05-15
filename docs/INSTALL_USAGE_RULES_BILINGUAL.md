# 安装、使用方法与规范 / Installation, Usage, And Rules

## A. 安装 / Installation

### 中文

克隆仓库：

```powershell
git clone https://github.com/leima-max/materials-research-general-agent.git
cd materials-research-general-agent
```

安装到 Codex 项目：

```powershell
.\install.ps1 -TargetProject "D:\your-codex-project"
```

覆盖已有文件：

```powershell
.\install.ps1 -TargetProject "D:\your-codex-project" -Force
```

安装并配置 Origin Pro MCP：

```powershell
.\install.ps1 -TargetProject "D:\your-codex-project" -SetupOriginProMcp
```

安装后验证：

```powershell
.\verify-package.ps1 -Root "D:\your-codex-project"
```

### English

Clone the repository:

```powershell
git clone https://github.com/leima-max/materials-research-general-agent.git
cd materials-research-general-agent
```

Install into a Codex project:

```powershell
.\install.ps1 -TargetProject "D:\your-codex-project"
```

Overwrite existing files:

```powershell
.\install.ps1 -TargetProject "D:\your-codex-project" -Force
```

Install and configure Origin Pro MCP:

```powershell
.\install.ps1 -TargetProject "D:\your-codex-project" -SetupOriginProMcp
```

Verify after installation:

```powershell
.\verify-package.ps1 -Root "D:\your-codex-project"
```

## B. 项目配置 / Project Configuration

### 中文

安装后必须配置：

- `PROJECT_VARIABLES.md`
- `DEVICE_CONFIG.md`

至少填写：

- 项目标题
- 研究领域
- 材料体系
- 样品或器件结构
- 主要目标
- 表征方法
- 数据类型
- 仿真范围
- 软件环境
- 输出风格
- 验证标准

### English

After installation, configure:

- `PROJECT_VARIABLES.md`
- `DEVICE_CONFIG.md`

At minimum, fill in:

- project title
- research field
- material system
- sample or device structure
- primary objectives
- characterization methods
- data types
- simulation scope
- software environment
- output style
- validation criteria

## C. 使用示例 / Usage Examples

### 中文

```text
请分析这组 UV-vis 数据并提取 Tauc 带隙。
请根据 XRD/GIWAXS 原始图像做积分并判断取向。
请把这个 CSV 画成期刊风格图，并输出可复现脚本。
请用 Origin Pro MCP 生成散点图、线性拟合并导出 PNG。
请根据这些文献做一份结构化综述。
请规划 COMSOL 光学吸收仿真并列出参数表。
```

### English

```text
Analyze this UV-vis dataset and extract the Tauc band gap.
Integrate this raw XRD/GIWAXS image and evaluate orientation.
Plot this CSV as a journal-style figure and provide a reproducible script.
Use Origin Pro MCP to create a scatter plot, perform linear fitting, and export PNG.
Prepare a structured literature review from these papers.
Plan a COMSOL optical absorption simulation and list the parameter table.
```

## D. 规范 / Rules

### 中文

- 不要在课题变量未配置时假设材料体系或器件结构。
- 数据分析必须保留原始数据路径、处理步骤、公式、单位和假设。
- 需要绘图时优先输出可编辑源文件或可复现脚本。
- 需要仿真时必须检查几何、材料参数、边界条件、激励源、求解器和验证标准。
- 使用外部软件时先确认本地安装、许可证和路径。
- 任何文件修改后都要运行最小验证。
- 对实验建议必须给出失败判据和下一步路线。

### English

- Do not assume a material system or device structure before project variables are configured.
- Data analysis must preserve raw-data paths, processing steps, formulas, units, and assumptions.
- For plotting, prefer editable source files or reproducible scripts.
- For simulation, check geometry, material parameters, boundary conditions, sources, solver settings, and validation criteria.
- For external software, confirm local installation, license, and paths.
- Run minimal verification after any file change.
- Experimental suggestions must include failure criteria and next steps.

## E. MCP 注意事项 / MCP Notes

### 中文

- Origin Pro MCP 只能在 Windows + Origin Pro + Windows Python 环境中工作。
- Zotero MCP 需要本地 Zotero 数据库路径和权限。
- MCP 配置文件生成后应检查 `config/mcporter.json` 中路径是否指向目标项目。

### English

- Origin Pro MCP works only with Windows, Origin Pro, and Windows Python.
- Zotero MCP requires a local Zotero database path and permissions.
- After MCP config generation, check that `config/mcporter.json` points to the target project.
