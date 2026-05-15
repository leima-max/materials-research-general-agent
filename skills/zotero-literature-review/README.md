# Zotero Literature Review Skill / Zotero 文献综述技能

## English

This skill guides an AI agent through Zotero-backed literature review work:

- inspect local Zotero readiness
- query Zotero through MCP
- normalize bibliography lists
- create or update Zotero collections
- import papers by DOI/URL/file
- apply tags and metadata corrections
- attach legal/open-access PDFs
- prepare Word dynamic Zotero citation workflows

It is intentionally verification-first. If Zotero MCP is not configured, the
agent should use Zotero exports, user-provided files, or verified web sources
instead of pretending to see the user's library.

## 中文

本技能用于指导 AI Agent 完成基于 Zotero 的文献工作：

- 检查本地 Zotero 可用性
- 通过 MCP 查询 Zotero
- 规范化参考文献列表
- 新建或更新 Zotero 分类
- 按 DOI/URL/文件导入文献
- 添加标签并修正元数据
- 添加合法开放获取 PDF
- 处理 Word Zotero 动态引用域流程

本技能强调“先验证后输出”。如果 Zotero MCP 没有配置成功，Agent 应改用 Zotero 导出文件、用户提供的文档或可验证网页来源，而不是假装已经访问到用户文献库。

## Files / 文件

- `SKILL.md`: Agent-facing operating instructions.
- `references/zotero-batch-import.md`: workflow for extracting references and importing them into Zotero.
- `references/zotero-pdf-autofetch.md`: workflow for PDF auto-fetch via MCP and Zotero plugin.
- `scripts/run_smoke_test.py`: checks local Zotero profile/database readiness.
- `scripts/run_mcp_smoke_test.py`: checks MCP read operations.

