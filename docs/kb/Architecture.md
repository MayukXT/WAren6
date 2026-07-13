---
title: WAren6 architecture map
tags: [architecture]
---

# Architecture

The two orchestrators are `waren6.ps1` (Windows-side acquisition + BouncyCastle decryption + archive + optional transfer) and `waren6.py` (unification, Store 8 crypto, validation, reports). They talk via CLI arguments and structured JSON artefacts written into a case folder.

## Pipeline (default hybrid mode)

```
waren6.ps1 (Windows shell)
  ├── Preflight (Doctor)
  ├── Acquisition
  │     ├── Locate LOCALAPPDATA\Packages\<WA-family>\LocalState (Get-AppxPackage)
  │     ├── Backup-mode file copy (robocopy /B /MT:8, sequential fallback)
  │     ├── ODUID lookup / --id override
  │     └── waren6.py --acquire  (dependency bootstrap only)
  ├── Decryption (BouncyCastle)
  │     ├── session.db, session.db-wal
  │     ├── nativeSettings.db, nativeSettings.db-wal
  │     ├── genericStorage.db, genericStorage.db-wal
  │     └── contacts.db
  ├── Runtime supplement (best-effort, hidden by default)
  │     ├── Set WebView2 registry: --remote-debugging-port=9222
  │     ├── Launch WhatsApp: explorer.exe shell:AppsFolder\<package-family>!App   ⚠ HARD-CODED
  │     ├── Poll http://127.0.0.1:9222/json/list  (90s budget)
  │     ├── CDP Runtime.evaluate → JS expression from Get-WAren6RuntimeExpression
  │     │     └── serialises Store 8 rows to JSONL
  │     └── Writes runtime\runtime_store8_messages.jsonl
  ├── waren6.py --unify
  │     ├── IndexedDB (ccl_chromium_reader) — 14 stores
  │     ├── Store 8 crypto profile + opaque decryption (optional)
  │     ├── SQLite (WAL-aware) — genericStorage, contacts, nativeSettings
  │     ├── Merge: exact msg_key, then bounded ±2s fuzzy timestamp
  │     ├── Runtime supplement merge (if JSONL present)
  │     ├── LID ↔ phone/JID resolution
  │     ├── Media indexing (--media)
  │     ├── Edit history reconstruction (same-msg_key variants + protocol events)
  │     ├── Quote body enrichment (SQL WITH … original_quotes)
  │     ├── Validation (source-vs-unified coverage counters)
  │     └── unified_whatsapp.db + validation_report.json + WAren6.manifest.json
  ├── Archive (tar.zst preferred, zip fallback)
  ├── SHA-256 of archive
  └── Optional Telegram transfer (split, encrypt, upload, verify)
```

## Modes

| Mode | Trigger | Uses live WA | Emits unified DB | Archive |
|---|---|---|---|---|
| Hybrid (default) | no flag | yes (best-effort) | yes | yes |
| Offline | `-f` / `--offline` | no | yes | yes |
| Acquire-only | `-a` | no | no (fallback: `WAren6_unify_later.txt`) | yes |
| Unify-only | `-u -c <case-or-archive>` | no | yes | no |
| Runtime-only | `-r -c <folder>` | yes | no | no (JSONL only) |
| Preflight | `-doc` | no | no | no |
| Dry-run | `--dry` | no | no | no |

## Key modules in `waren6.py`

| Region | Lines | Purpose |
|---|---|---|
| Schema | 94–342 | `UNIFIED_SCHEMA`, split table/index emit |
| Connection tuning | 351–358 | `PRAGMA journal_mode=MEMORY`, mmap 256 MB, cache 128 MB |
| Store 8 crypto | 600–911 | HKDF + AES-128-CBC + PKCS#7 parse-guarded plaintext detection |
| Salt hunt | 1044–1142 | Offline artefact scan for HKDF salt candidates |
| IndexedDB read | 1821–1982 | ccl_chromium_reader iterate over 14 stores |
| WAL-aware SQLite open | 1993–2200 | Native-WAL path + manual page reassembly fallback |
| Merge / dedup | 2775–3220 | exact (chat_jid, ts) + bounded ±2s fuzzy timestamp |
| Runtime supplement | 1556–1629 | JSONL parse + merge |
| Edit reconstruction | 3440–3521 | Same-msg_key variants + protocol event folding |
| Media indexing | 3722–3893 | rglob → SHA-256 → filename join → media_assets |
| Reports | 4272–4400+ | HTML / JSONL / CSV / TSV / PDF writers |
| CLI entry | 4553–4885 | argparse + subcommand dispatch |

## Data flow: single-writer, single-threaded

Currently all work in `waren6.py` runs in one Python process, one thread. IndexedDB read → SQLite insert → media hash all block one another. On modest field-kit hardware this is the single largest lever.

See [[perf/Bottlenecks]] for the ranked opportunities.
