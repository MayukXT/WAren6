---
title: "ADR-004: Schema-agnostic session-key recovery"
tags: [adr, crypto, compat]
status: Accepted
date: 2026-07-07
---

# ADR-004: Schema-agnostic session-key recovery

## Status

Accepted (2026-07-07). Landed in the same commit as ADR-003.

## Context

The original PS1 flow decrypted `session.db-wal` and byte-scanned it for a specific 3-byte SQLite record header shape (`0x03 kType vType`) to find WhatsApp client keys. `Get-WalSettingsData` (`waren6.ps1:3458`) parses only records that:

- Have header size varint == `0x03` (exactly 2-column tables: key + blob value).
- Have key column type in `{0x01, 0x08, 0x09}` (small integer) with key value 0-10.
- Have blob column type in the range `0x2C-0x8C` (16-64 byte BLOBs).

On WhatsApp Desktop Windows 11 Build 22000 (`ANIRBANDEYPC` field report, 2026-07-06) this scanner returned zero records and the pipeline hard-failed with:

```
CRITICAL: No client keys found in session.dec.db-wal.
The WAL file may be empty or in an unexpected format.
```

Two independent failure modes explain this:

1. **WAL was checkpointed.** WA cleanly closed at some point, or Windows fired an auto-checkpoint on WAL size threshold, or newer WA builds checkpoint more aggressively during idle. After checkpoint the WAL retains its 32-byte file header but has zero frames.
2. **Session table schema changed.** WA added columns (or the record layout otherwise shifted), so header size is now `0x04+` rather than `0x03`.

Both failures produce the same visible symptom, and both leave the client keys accessible in `session.dec.db` (the decrypted main file), just not where the legacy scanner looks.

## Decision

Rewrite the client-key recovery to be schema-agnostic and self-validating.

Introduce two tiers:

**Tier 1 (fast path, backward-compatible):**

- Call legacy `Get-WalSettingsData` on `session.dec.db-wal`.
- If it returns records, iterate from last to first; for each valid 32/48-byte blob, compute SHA-1 and check for `sessions/<uppercase-40-hex>/` on disk.
- First match wins. Preserves behavior for WA builds that still use the 2-column shape.

**Tier 2 (schema-agnostic fallback):**

- `Find-SessionClientKeyCandidates` scans both `session.dec.db-wal` (past 32-byte WAL header) and `session.dec.db` (past 100-byte SQLite header).
- `Find-SqliteBlobCandidates` is a schema-agnostic scanner that:
  - Tries header sizes 3-8 (covers 2-7 column tables).
  - Parses column type varints (single-byte only; multi-byte header extensions are rare in this workload).
  - Uses `Get-SqliteRecordSizeForType` to compute per-column data-region offsets.
  - Extracts any column whose serial-type varint is `12 + 2*N` where N is in `{32, 48}` (the two known WA client-key sizes).
- Every candidate blob is SHA-1'd. First candidate whose hash matches an existing `sessions/<40-hex>/` directory wins.
- SHA-1-matching against real session dirs is the ground truth: the `sessions/<hex>/` layout is set by the WhatsApp app itself, so matching against it is schema-agnostic and rejects false-positive blobs the scanner picks up from other pages.

**Same tier-cascade** for `nativeSettings.dec.db-wal` -> `nativeSettings.dec.db` via `Get-SettingsRecords` + `Find-SqliteSettingsRecords`, which uses the same schema-agnostic pattern but returns objects shaped identically to `Get-WalSettingsData` so downstream code is unchanged.

**Diagnostic dump on total failure:** if both tiers find nothing, we emit file sizes, session directory names, candidate counts, and sample candidate previews (source, size, offset, first-16-hex) so the next debugging round has actionable data instead of a mystery abort.

## Consequences

**Positive:**

- Newer WA Desktop builds where the WAL is checkpointed or the record layout changed continue to work.
- Discovery inverts: instead of "trust the WAL, then find its session dir," we do "read the session dirs, find the key that hashes to one of them." This is more robust across schema changes.
- Blob false positives are cheap: they're SHA-1'd and rejected via `Test-Path`.

**Negative:**

- Tier 2 scan is O(file size) with a per-byte header-shape check. On a typical multi-MB session.dec.db this runs in a few seconds -- acceptable, since Tier 1 usually succeeds when the DB shape is unchanged.
- If WhatsApp ever switches from SHA-1 to a different digest for session dir names, this validation approach fails. The diagnostic dump surfaces that immediately.
- If future WA builds use client keys of a size other than 32 or 48 bytes, we need to extend `AcceptBlobSizes` in `Find-SqliteBlobCandidates`.

## Alternatives Considered

1. **Open the SQLite `.db` file with `System.Data.SQLite` and query the settings table directly.** Rejected: PS 5.1 doesn't ship SQLite; bundling `System.Data.SQLite.Core.dll` adds ~1.5 MB to the field kit and a native dependency. Byte-scanning is battle-tested and dependency-free.
2. **Shell out to `sqlite3.exe`.** Rejected: not present by default on Windows 10/11.
3. **Loosen the legacy `Get-WalSettingsData` to accept larger headers.** Would still miss the case where WAL is truly empty (checkpointed). Doesn't solve the primary failure mode.
4. **Ask the examiner to bundle a decrypted key list.** Rejected: undermines the "acquire on target, unify anywhere" workflow.

## References

- `waren6.ps1:3547` -- `Get-SqliteRecordSizeForType`.
- `waren6.ps1:3572` -- `Find-SqliteBlobCandidates` (schema-agnostic).
- `waren6.ps1:3661` -- `Find-SessionClientKeyCandidates` (combines WAL + main DB).
- `waren6.ps1:3813` -- `Find-SqliteSettingsRecords` (nativeSettings shape-compatible).
- `waren6.ps1:3891` -- `Get-SettingsRecords` (legacy-first cascade).
- `waren6.ps1:3920` -- `Test-ClientKeyAgainstSessionsDir` (SHA-1 validation).
- `waren6.ps1:4230+` -- rewritten Tier 1 / Tier 2 recovery flow.
- Field report 2026-07-06 (`ANIRBANDEYPC` transcript in NOTES.md).
