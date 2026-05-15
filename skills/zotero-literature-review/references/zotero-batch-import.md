# Zotero Batch Import And Collection Workflow

## English

Use this workflow when the user asks to extract a bibliography from a document,
create a Zotero collection, and add the referenced papers.

### Preferred Route

1. Extract references into a normalized table:
   source index, raw reference, title, year, first author, DOI, priority marker.
2. Resolve metadata by DOI first.
3. If DOI is absent, query Crossref or another authoritative metadata source by
   exact title and accept only high-confidence title/year matches.
4. Check whether the target collection already exists.
5. If MCP Web API or hybrid write mode is configured, use MCP write tools.
6. Verify collection key, item count, metadata, tags, and attachments.

### MCP Write Mode

Local Zotero mode is often read-oriented. For writes, configure Web API or
hybrid mode:

```text
ZOTERO_LOCAL=true
ZOTERO_LOCAL_LIBRARY_ID=0
ZOTERO_LIBRARY_ID=YOUR_ZOTERO_USER_OR_GROUP_ID
ZOTERO_LIBRARY_TYPE=user
ZOTERO_API_KEY_FILE=/path/outside/repo/zotero_api_key.txt
```

### Zotero Connector Fallback

Zotero Desktop exposes Connector endpoints at `http://127.0.0.1:23119`.
Connector import can be useful for RIS/BibTeX imports into the currently
selected target, but it is not a full collection-management API. Verify imports
afterward through MCP or read-only database checks.

### SQLite Last Resort

Direct SQLite writes should be a last resort:

1. Close Zotero gracefully.
2. Verify the database is not locked.
3. Back up `zotero.sqlite`.
4. Enable `PRAGMA foreign_keys=ON`.
5. Write only the minimal rows needed.
6. Reopen Zotero and verify through Zotero itself.

Never write to a live Zotero database while Zotero is running.

## 中文

当用户要求从 Word/PDF/文本中提取参考文献、新建 Zotero 分类并导入文献时，使用本流程。

### 推荐路线

1. 将参考文献提取为规范表格：原始编号、原始条目、题名、年份、第一作者、DOI、重点标记。
2. 优先用 DOI 解析元数据。
3. 如果没有 DOI，用精确题名查询 Crossref 或其他权威元数据源，只接受题名和年份高度一致的结果。
4. 检查目标 Zotero collection 是否已经存在。
5. 如果已配置 MCP Web API 或 hybrid 写入模式，优先使用 MCP 写入工具。
6. 最后验证 collection key、条目数量、元数据、标签和附件。

### MCP 写入模式

Zotero local 模式通常适合读取。写入建议配置 Web API 或 hybrid 模式：

```text
ZOTERO_LOCAL=true
ZOTERO_LOCAL_LIBRARY_ID=0
ZOTERO_LIBRARY_ID=YOUR_ZOTERO_USER_OR_GROUP_ID
ZOTERO_LIBRARY_TYPE=user
ZOTERO_API_KEY_FILE=/path/outside/repo/zotero_api_key.txt
```

### Zotero Connector 兜底

Zotero Desktop 在 `http://127.0.0.1:23119` 暴露 Connector 端点。Connector 可用于把 RIS/BibTeX
导入当前选中的目标，但它不是完整的 collection 管理 API。导入后必须用 MCP 或只读数据库检查验证。

### SQLite 最后兜底

直接写 SQLite 只能作为最后手段：

1. 优雅关闭 Zotero。
2. 确认数据库没有锁定。
3. 备份 `zotero.sqlite`。
4. 启用 `PRAGMA foreign_keys=ON`。
5. 只写入完成任务所需的最少行。
6. 重启 Zotero 并在 Zotero 中验证。

不要在 Zotero 运行时直接写 live database。

