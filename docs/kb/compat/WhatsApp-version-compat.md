---
title: WhatsApp Desktop version compatibility
tags: [compat, version]
updated: 2026-07-04
---

# WhatsApp Desktop version compatibility

WAren6 targets WhatsApp Desktop (UWP package, WebView2 host). This page tracks the version-fragile assumptions and the risk of breakage on newer builds.

## What is already handled

- **WAL-only DBs (v2.3000+):** `_apply_wal_and_open` (`waren6.py:1993`) opens the DB with its companion WAL via native SQLite first, and only falls back to manual page reassembly if that fails. This is the correct order.
- **Package family lookup for acquisition:** `waren6.ps1` uses `Get-AppxPackage` to find the WhatsApp Desktop package family dynamically; it is not hard-coded.
- **IndexedDB path candidates:** `extract_indexeddb` (`waren6.py:1832–1837`) tries three path shapes so both `EBWebView_Default/…` and `EBWebView_Default/Default/IndexedDB/…` copy layouts work.
- **Store 8 opaque body preservation:** rows are kept and labeled `opaque_unresolved` rather than silently dropped when the network salt is missing.

## Known fragile spots (worth a re-verify on the latest build)

### 1. Runtime launcher hard-codes the package family

`waren6.ps1:2928`
```powershell
Start-Process "explorer.exe" "shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App" -WindowStyle Hidden | Out-Null
```

If Meta re-signs or re-publishes under a new family name, this launch fails silently. The runtime capture path degrades to "no supplement" and the operator sees warnings but no fatal error.

**Fix candidate:** resolve the AppUserModelID via `Get-AppxPackage | Select-Object -First 1 -ExpandProperty PackageFamilyName` (already used elsewhere), then `Get-StartApps | Where-Object AppID -like "$familyName!*"`.

### 2. Runtime JS expression assumes internal store shape

`waren6.ps1: Get-WAren6RuntimeExpression` (search that symbol). The JS is evaluated via CDP `Runtime.evaluate` and expected to serialise Store 8 rows to JSONL. If WhatsApp refactors the internal message store keys, this returns empty and the retry loop wastes ~60 s before giving up.

**Fix candidate:** detect empty payload earlier, log the actual JS exception if present, and short-circuit rather than retry 20 × 3 s.

### 3. WebView2 registry override is per-machine

`waren6.ps1:3140` sets `HKCU:\Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments\WhatsApp.Root.exe`. If the WebView2 runtime executable name changes in a future WhatsApp build (e.g. renamed to `WhatsAppDesktop.exe`), the debugger port never gets applied.

**Fix candidate:** on newer versions, also probe `Get-Process` for WA's WebView2 child process, discover its exe leaf name, and set the registry value for that name too.

### 4. IndexedDB store IDs are hard-coded

`waren6.py:1881–1894`
```python
store_map = {
    4: 'contact', 5: 'blocklist', 7: 'chat', 8: 'message',
    9: 'message-info', 10: 'participant', 21: 'group-metadata', ...
}
```

`ccl_chromium_indexeddb` also exposes `object_stores_by_db_id` — we could iterate names dynamically and map by name instead of ID. WhatsApp's model-storage store IDs have been stable but this is a silent-failure surface.

**Fix candidate:** dynamic name-based lookup with the current dict as a fallback for offline evidence where names are not readable.

### 5. Assumption of `sessions/<session-id>/…` layout

Newer builds might store `contacts.db`, `nativeSettings.db`, `genericStorage.db` in a different layout. The acquisition code enumerates every session subfolder, but the unifier's SQLite extraction expects specific filenames.

**Fix candidate:** glob for `*.db` inside each session folder and identify by SQLite schema (`sqlite_master`), not by filename.

### 6. Runtime capture depends on WebView2 remote-debugging protocol

Chromium may deprecate or tighten remote debugging in future WebView2 versions (they have already added flags like `--remote-debugging-pipe`). A signed release might disable it entirely on locked-down enterprise fleets.

**Not much we can do here — flag as a research/reliability risk in [[NOTES]] rather than a code fix.**

## Verification checklist for a new WhatsApp Desktop release

Every time WhatsApp Desktop ships a new visible version, run:

1. Fresh install, log in, send a mix of text/image/video/reaction messages.
2. `powershell -ExecutionPolicy Bypass -File .\waren6.ps1 -doc` — expect all checks green.
3. `powershell -ExecutionPolicy Bypass -File .\waren6.ps1 -m` — expect a normal case.
4. Open `unified_whatsapp.db` in Reader — expect message text, media, reactions, quotes to render.
5. Compare `validation_report.json` counts to `EXTRACTION_EVENTS`. Store 8 opaque rows > 0 with `store8_runtime_decoded_messages` also > 0 is the healthy shape for hybrid mode.
6. `messages_missing_local_media` should equal the count of files WhatsApp has not downloaded to disk yet — not a bulk regression.

## Test coverage today

`tests/test_waren6_runtime_validation.py` and `tests/test_waren6_hybrid_media.py` cover pipeline invariants against synthetic fixtures. Neither exercises a *real* WhatsApp Desktop install. The verification above must be manual, on a real box.
