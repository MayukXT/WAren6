---
title: Running notes
tags: [scratchpad]
---

# NOTES

Rolling scratchpad. Trim quarterly. Datestamp each entry.

## 2026-07-04 — Initial audit for perf + newer-WA compatibility

- Graphify seeded: 1041 nodes / 2522 edges / 53 communities. See `graphify-out/GRAPH_REPORT.md`.
- Bottleneck audit landed in [[perf/Bottlenecks]]. Top 6 hot paths ranked with line refs.
- Version-fragile assumptions listed in [[compat/WhatsApp-version-compat]]. Only one truly hard-coded package family name (`waren6.ps1:2928`), and even that path is a fallback launcher — the acquisition side uses `Get-AppxPackage`.
- Zero concurrency in `waren6.py` (grep `ThreadPool|multiprocessing|asyncio|threading.` returned no matches). Biggest single lever for slower/older evidence machines.
- The three known reliability risks under newer WhatsApp Desktop:
  1. WAL-only checkpointing (v2.3000+) — `_apply_wal_and_open` already handles this. See `waren6.py:1993`.
  2. Store 8 opaque `_data` rows requiring WebWA network salt — hybrid runtime path covers many.
  3. Runtime capture depends on injecting a JS expression via WebView2 DevTools; if WhatsApp's internal store/module names change, the expression in `Get-WAren6RuntimeExpression` breaks silently.

## 2026-07-07 -- Optimization sprint 2 + CRITICAL WA schema fix

Landed after a multi-agent research workflow that mapped the unify pipeline stage-by-stage and cross-referenced against SQLite/LevelDB/HKDF background research. All changes preserve extraction yield; all 104 tests pass.

**Field incident (highest priority):** report from `ANIRBANDEYPC` (Win11 Build 22000) showed the acquisition failing with `CRITICAL: No client keys found in session.dec.db-wal`. Root cause: WA Desktop had checkpointed the WAL into `session.dec.db` (or the session table changed shape entirely), so the legacy 3-byte-header byte scanner returned nothing. Fixed with schema-agnostic Tier 2 fallback (see [[adr/ADR-004-session-key-schema-agnostic]]).

**Code changes (waren6.py):**

- HKDF-SHA256 output memoization keyed by `(ikm, salt, info, length)` with bounded (`cap=4096`) FIFO cache. `algorithms.AES(key)` object cache (`cap=512`) too. Honest speedup: 2-5x on the Store 8 opaque stage when triggered (the earlier "25-75x" claim was HKDF-call-only, not stage-wide -- Cipher-object allocation dominates end-to-end).
- `--fast-salt-hunt` CLI flag: opt-in early exit when >=3 validated candidates AND 32 consecutive files with no new hits. Default stays exhaustive because multi-salt cases exist (WA reinstall, salt rotation) and dropping later candidates loses yield.
- `create_unified_indexes` wraps all 18 `CREATE INDEX` in one `BEGIN/COMMIT`; temporarily bumps `PRAGMA cache_size=-262144` (256 MiB) during index build only, restores caller's 128 MiB after. Cache-locality win, not fsync (fsync was already gone via `journal_mode=MEMORY`).
- `--profile` CLI flag: dumps per-stage `time.perf_counter` timings to `unify_profile.json` alongside output DB. Stage records: `extract_indexeddb`, `load_decrypted_sqlite`, `build_lid_resolver`, `build_unified_db`, `media_index`.
- `--media-only <path-to-unified.db>` CLI flag: run only media indexing against an existing unified DB. Enables deferring the O(files*size) SHA-256 pass off the target machine.
- Cross-OS unify guard verified: no `winreg`, `win32*`, `ctypes.WinDLL` at import time; `--unify` code path is Linux/macOS-clean.

**Code changes (waren6.ps1):**

- New `Get-SqliteRecordSizeForType` helper: table lookup for SQLite serial-type varint byte sizes.
- New `Find-SqliteBlobCandidates`: schema-agnostic scanner accepting header sizes 3-8 (2-7 column tables) and enumerating any column whose type varint encodes a 32 or 48 byte BLOB.
- New `Find-SessionClientKeyCandidates`: combines legacy `Get-WalSettingsData` fast path with the broad scanner across both WAL and main .db.
- New `Test-ClientKeyAgainstSessionsDir`: SHA-1 candidate blob and check for existing `sessions/<40-hex>/` directory. Schema-agnostic validation.
- New `Find-SqliteSettingsRecords` + `Get-SettingsRecords`: same tier-cascade for `nativeSettings.dec.db-wal` -> `nativeSettings.dec.db` so DB-key discovery survives the same schema shift.
- Rewrote client-key recovery block: two-tier flow (Tier 1 legacy, Tier 2 broad+SHA-1-match). Full diagnostic dump on total failure (file sizes, sessions dir names, candidate previews) so next debugging round has data.
- ASCII-only strings throughout the new code (PS 5.1 default codepage doesn't handle em-dash / right-arrow -- caused parse errors on first attempt).

**Deferred (need real numbers from `--profile` first):**

- Store 8 parse + genericStorage fuzzy merge `ProcessPoolExecutor`. Adversarial review flagged the estimate as oversold on target (Windows spawn cost + pickle) and requires ordering-determinism guard to preserve reproducibility.
- LevelDB pipeline read + parallel V8/Blink deserialize. Depends on `cryptography` actually releasing the GIL (OpenSSL-backed: yes; PyCryptodome fallback: no); requires runtime backend detection.
- Commit consolidation 29 -> 3. Adversarial review corrected the estimate from 3-5s down to 300-800ms because `journal_mode=MEMORY + synchronous=OFF` are already set. Small ROI, real regression risk if `isolation_level` misconfigured. Revisit only if `--profile` shows this dominates.

**Docs updates:**

- `LLM.txt`: appended Performance Reality, Split-Machine Workflow, Flags Added, What NOT to Do, Cross-OS Unify, and Session Key Recovery sections. Also updated pointers at the tail.
- `docs/kb/perf/Bottlenecks.md`: replaced with real research-backed ranking, cross-cutting invariants, and deferred items.
- `docs/kb/adr/ADR-003-split-machine-workflow.md`: new.
- `docs/kb/adr/ADR-004-session-key-schema-agnostic.md`: new.

## Backlog

- Ask LO to run the fixed `waren6.ps1` on `ANIRBANDEYPC` and confirm the Tier 2 SHA-1-match path finds the client key. If it still fails, the diagnostic dump will tell us what shape WA moved to.
- Add a small microbench harness in `tests/perf/` for regression flags (not for correctness).
- Manual verification pass on very latest WhatsApp Desktop build (post 2.3010).
