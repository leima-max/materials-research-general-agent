# Zotero PDF Auto-Fetch Workflow

## English

Use this workflow when the user asks whether Zotero can automatically find,
download, link, or attach PDFs for newly added items.

### Legal Sources Only

Automation should use only:

- open-access publisher PDFs
- Unpaywall OA locations
- arXiv
- PubMed Central
- Semantic Scholar `openAccessPdf`
- institution-authorized access when the user confirms they are allowed to use it

Do not automate gray-market resolvers.

### MCP Behavior

`zotero_add_by_doi(..., attach_mode="auto")` should:

1. create the Zotero item
2. search legal/OA sources for a PDF URL
3. try to download and attach a valid PDF
4. if a candidate URL exists but direct download fails, create a
   `PDF (linked URL)` attachment
5. if no candidate URL exists, report that no open-access PDF was found

This linked-url fallback is useful, but it does not expand the discovery range:
it only preserves a URL that MCP already found.

### Zotero Plugin Behavior

The bundled plugin observes newly added regular items and calls:

```js
Zotero.Attachments.addAvailableFiles(items, {
  methods: ["doi", "url", "oa"]
});
```

Because it runs inside Zotero, it can use Zotero's internal DOI/URL/OA lookup
pipeline and progress UI.

### Verification

After adding items, verify:

- the parent item exists
- there is at most one intended PDF/EPUB file attachment
- linked URL attachments have `contentType=application/pdf`
- stored PDF files exist under Zotero storage
- failures are reported as "no legal/open candidate found" rather than hidden

## 中文

当用户询问 Zotero 是否能自动为新增条目查找、下载、链接或添加 PDF 时，使用本流程。

### 只使用合法来源

自动化只应使用：

- 开放获取的出版社 PDF
- Unpaywall OA 链接
- arXiv
- PubMed Central
- Semantic Scholar `openAccessPdf`
- 用户确认已授权的机构访问来源

不要自动化灰色解析器。

### MCP 行为

`zotero_add_by_doi(..., attach_mode="auto")` 应该：

1. 创建 Zotero 条目；
2. 从合法/OA 来源查找 PDF URL；
3. 尝试下载并添加有效 PDF；
4. 如果找到了候选 URL 但直接下载失败，则创建 `PDF (linked URL)` 附件；
5. 如果没有候选 URL，则明确报告没有找到开放获取 PDF。

linked-url 兜底很有用，但它不会扩大 MCP 的发现范围：它只能保留 MCP 已经找到的 URL。

### Zotero 插件行为

随包插件会监听新增普通条目，并调用：

```js
Zotero.Attachments.addAvailableFiles(items, {
  methods: ["doi", "url", "oa"]
});
```

因为它运行在 Zotero 内部，所以可以复用 Zotero 自己的 DOI/URL/OA 查找流程和进度界面。

### 验证

添加条目后检查：

- 父条目存在；
- 预期的 PDF/EPUB 附件存在，且没有不必要重复；
- linked URL 附件的 `contentType=application/pdf`；
- stored PDF 文件确实存在于 Zotero storage；
- 找不到 PDF 时要明确报告“未找到合法/开放候选来源”，不能静默失败。

