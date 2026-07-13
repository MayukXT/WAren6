---
title: Performance bottlenecks (modest CPUs)
tags: [perf, bottleneck]
updated: 2026-07-07
---

# Bottlenecks

Target: modest field-kit machines — older laptops, low-power evidence PCs, dual-core CPUs, mechanical or slow SATA SSD, 4-8 GB RAM. All estimates below are from code inspection; use `python waren6.py --unify <case> --profile` to get real per-stage numbers.

## Ranked (default hybrid run, ~30k messages)

| # | Stage | File:line | Cost | Root cause | Fix status |
|---|---|---|---|---|---|
| 1 | Store 8 parse + genericStorage fuzzy merge | `waren6.py:2843-3046` | 5-15s (dominant) | Single-threaded Python loop, GIL-bound, per-record `(chat_jid, ts +/- 2s)` dict lookup | not-fixed-yet (see deferred) |
| 2 | Store 8 opaque HKDF+AES loop | `waren6.py:720-784, 854-912` | 5-15s if triggered | `(ikm x salt x info)` cartesian retried per record; no memoization pre-sprint | FIXED 2026-07 (bounded `(ikm, salt, info, length)` dict cache + `algorithms.AES(key)` object cache, both capped, FIFO evict). Honest speedup 2-5x on this stage. |
| 3 | V8/Blink structured-clone deserialize | inside `ccl_chromium_reader` | 1-4s | Pure Python, sequential, GIL-held | not-fixed (upstream) |
| 4 | Deferred index creation | `waren6.py:3286` (`create_unified_indexes`) | 1-3s | 18 `CREATE INDEX` with per-statement pager flush + cache churn pre-sprint | FIXED 2026-07 (single `BEGIN/COMMIT` wrapping all 18 statements; PRAGMA `cache_size=-262144` temporarily bumped to 256 MiB during index build only, restored after) |
| 5 | Snappy decompression during LevelDB read | inside `ccl_chromium_reader` | 1-3s | Pure-Python `ccl_simplesnappy` on every block | not-fixed (upstream limit) |
| 6 | Salt hunter file scan | `waren6.py:1106-1266` | 2-10s if triggered | No early exit; scans all 2000 files even after first validated salt | FIXED behind flag: `--fast-salt-hunt` opt-in (>=3 validated + 32 dry files -> break). Default remains exhaustive. |
| 7 | 29 tiny `conn.commit()` calls | scattered `waren6.py:2712..3994` | 300-800ms | Per-stage commit; `journal_mode=MEMORY` makes each cheap but not free | DEFERRED (real save is small; risk of accidentally regressing to autocommit is real). Revisit if `--profile` shows this dominates. |
| 8 | `genericStorage.dec.db` WAL page-merge fallback | `waren6.py:1994-2100` | rare, but heavy | Only fires if primary WAL-copy fails on corruption | not-fixed (correct fallback) |

## Cross-cutting invariants (do NOT break)

- **Forensic reproducibility.** Identical input -> identical output. Any future parallelization MUST enforce deterministic ordering (`ProcessPoolExecutor.map(chunksize=N)` or explicit tie-break by row_id). `as_completed()` is off-limits for anything that writes rows.
- **Yield preservation.** No fix should drop rows silently. All FIXED items above pass all 104 tests.
- **Cross-OS unify.** `--unify` code path contains no Windows-only imports (verified 2026-07). Path handling uses `pathlib.Path` throughout. Do not add `winreg`, `win32*`, or `ctypes.WinDLL` calls to `unify` / `build_unified_db` / anything they transitively call.

## Instrumentation

- `python waren6.py --unify <case> --profile` writes `unify_profile.json` alongside the output DB with per-stage `perf_counter` timings and stage metadata.
- Rerun the ranked table above with real numbers before doing more perf work. Ranking may reshuffle.

## Deferred (need real numbers first)

- **Pipeline LevelDB read + parallel V8/Blink deserialize.** Medium effort. Adversarial review flagged: N `IndexedDb()` instances on the same LevelDB dir re-Snappy-decompress the same blocks (net zero win); the correct shape is one reader thread yielding raw `(key_prefix, value_bytes)` tuples to a worker pool. Only helps if `cryptography` genuinely releases the GIL (OpenSSL-backed path, yes; pure-Python PyCryptodome fallback, no).
- **Store 8 parse `ProcessPoolExecutor`.** Medium effort. Windows uses spawn (not fork) so each worker re-imports `waren6.py` (~500ms-1s startup) and receives `generic_entries_by_chat_ts` via pickle (100-500ms per worker for a typical 60k-entry dict). Realistic net win on a dual-core target is 1.3-1.6x, not 2-3x. Also requires ordering-determinism guard (`map(chunksize=N)` and tie-breakers) so we don't break reproducibility.
- **Commit consolidation 29 -> 3.** Adversarial review corrected the estimate from 3-5s down to 300-800ms because `journal_mode=MEMORY + synchronous=OFF` are already set. Small ROI, non-trivial regression risk if `isolation_level` is misconfigured. Revisit only if `--profile` shows commits are a real slice.
- **Report export streaming.** Small effort but unclear ROI without measurement.

## Split-machine deferrals

If unification is intolerably slow on the target, use the split-machine workflow (see `ADR-003`). Two additional flags land large deferrals off the target:

- `--media-only <path-to-unified.db>` — run only media indexing against an existing unified DB. Defers the O(files x size) SHA-256 pass off the target.
- `--fast-salt-hunt` — opt-in; break after >=3 validated candidates AND 32 dry files. Only for cases where you accept "first valid salt wins" over exhaustive salt discovery.

## What is already good

- SQLite tuning at `configure_unified_output_connection` (waren6.py:352) is aggressive and correct: `journal_mode=MEMORY`, `synchronous=OFF`, `cache_size=-131072` (128 MiB), `mmap_size=268435456` (256 MiB), `locking_mode=EXCLUSIVE`.
- Indexes are created after bulk inserts, wrapped in one BEGIN/COMMIT (`waren6.py:347`).
- Media indexing uses `ThreadPoolExecutor(max_workers<=4)` with GIL release inside `hashlib.update` (`waren6.py:3822+`).
- Variant-dedup uses a single `SELECT target_msg_key, COUNT(*) ... GROUP BY` prefetch instead of per-key COUNT.
- Native-WAL-first strategy at `waren6.py:1993` with manual page-merge fallback (see ADR-001).
- BouncyCastle assembly loaded once at script scope in `Start-WAren6` (no per-frame `LoadWithPartialName`).
