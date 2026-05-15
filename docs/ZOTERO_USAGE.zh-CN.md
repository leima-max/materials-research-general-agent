# Zotero 技能包使用说明

## 1. 安装 Zotero

先安装 Zotero Desktop，并确保 Zotero Connector 本地端点可用。默认情况下，冒烟测试会检查
`~/Zotero/zotero.sqlite`，也可以通过环境变量覆盖：

```powershell
$env:ZOTERO_EXE = "C:\Program Files\Zotero\zotero.exe"
$env:ZOTERO_DATA_DIR = "$HOME\Zotero"
```

## 2. 安装 MCP server

```powershell
cd mcp/zotero-mcp-server
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[all]"
```

只读 local 模式：

```powershell
$env:ZOTERO_LOCAL = "true"
$env:ZOTERO_LOCAL_LIBRARY_ID = "0"
```

读写 hybrid 模式：

```powershell
$env:ZOTERO_LOCAL = "true"
$env:ZOTERO_LOCAL_LIBRARY_ID = "0"
$env:ZOTERO_LIBRARY_ID = "YOUR_ZOTERO_USER_ID"
$env:ZOTERO_LIBRARY_TYPE = "user"
$env:ZOTERO_API_KEY_FILE = "C:\path\outside\repo\zotero_api_key.txt"
```

本地 Zotero Desktop 的 library ID 通常是 `0`；Web API 写入使用 zotero.org 的数字 user ID 或 group ID。

## 3. 配置 Codex 或其他 MCP 客户端

使用 `config/codex-config.example.toml` 作为模板。不要把真实密钥写入配置文件，优先使用
`ZOTERO_API_KEY_FILE`。

## 4. 安装文献综述 skill

把 `skills/zotero-literature-review` 复制到 Agent 的技能目录。该 skill 适用于：

- 基于 Zotero 文献库写综述
- 从 Word/文本参考文献中提取题录并匹配 DOI
- 根据参考文献列表创建 Zotero collection
- 检查引用、元数据和附件
- 处理 Word Zotero 动态引用域
- 判断和配置 PDF 自动匹配策略

## 5. 构建 Zotero 插件

```powershell
powershell -ExecutionPolicy Bypass -File .\plugins\zotero-auto-pdf-fetch\validate.ps1
powershell -ExecutionPolicy Bypass -File .\plugins\zotero-auto-pdf-fetch\package.ps1
```

然后在 Zotero 插件管理器中安装生成的 `.xpi`。

## 6. 验证

```powershell
python skills/zotero-literature-review/scripts/run_smoke_test.py
python skills/zotero-literature-review/scripts/run_mcp_smoke_test.py
powershell -ExecutionPolicy Bypass -File .\scripts\sanitize_check.ps1
```

## 7. PDF 自动匹配行为

MCP 的 `attach_mode="auto"` 会尝试合法开放获取来源。如果找到了 PDF URL 但直接下载失败，会创建
PDF 链接附件；如果连候选 PDF URL 都没找到，就不会创建 linked-url 附件。

Zotero 插件适合真正的 Zotero 桌面端自动化，因为它在 Zotero 内部调用
`Zotero.Attachments.addAvailableFiles()`，能复用 Zotero 自身的 DOI/URL/OA 查找流程。

