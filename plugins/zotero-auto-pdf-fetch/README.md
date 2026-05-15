# Zotero Auto PDF Fetch

Zotero 7 plugin that observes newly added regular items and runs Zotero's
internal Find Full Text workflow for eligible items that do not already have a
PDF or EPUB attachment.

The plugin calls:

```js
Zotero.Attachments.addAvailableFiles(items, { methods: ["doi", "url", "oa"] });
```

## Behavior

- Listens for Zotero `item` `add` notifications.
- Waits `20s` by default so Zotero Connector imports can finish adding their
  own attachments before the plugin checks the item.
- Skips notes, attachments, annotations, feed items, deleted items, libraries
  where files are not editable, and items without DOI/URL.
- Skips items that already have a PDF or EPUB attachment.
- Uses Zotero's own PDF retrieval pipeline and progress window.
- Processes at most `25` newly added items per batch by default.

## Safety

Default methods are `doi,url,oa`.

Custom resolvers are disabled by default via:

```js
pref("extensions.zotero-auto-pdf-fetch.includeCustomResolvers", false);
```

Keep this disabled unless every custom resolver in Zotero is legal and
authorized for automated use. This workspace intentionally avoids automating
gray-market resolvers.

## Build

From the workspace root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\zotero-auto-pdf-fetch\validate.ps1
powershell -ExecutionPolicy Bypass -File .\tools\zotero-auto-pdf-fetch\package.ps1
```

The XPI is written to:

```text
tools\zotero-auto-pdf-fetch\dist\zotero-auto-pdf-fetch-0.1.8.xpi
```

## Install

In Zotero:

1. Open `Tools -> Plugins`.
2. Drag the `.xpi` file into the Plugins window, or use the gear menu and
   choose `Install Add-on From File...`.
3. Restart Zotero if prompted.

## Preferences

The plugin uses these Zotero preferences:

```js
extensions.zotero-auto-pdf-fetch.enabled = true
extensions.zotero-auto-pdf-fetch.delayMS = 20000
extensions.zotero-auto-pdf-fetch.sameDomainRequestDelayMS = 1000
extensions.zotero-auto-pdf-fetch.maxBatchSize = 25
extensions.zotero-auto-pdf-fetch.methods = "doi,url,oa"
extensions.zotero-auto-pdf-fetch.includeCustomResolvers = false
```

These can be changed through Zotero's Config Editor.
