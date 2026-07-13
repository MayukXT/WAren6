---
title: ADR-001 — Native-WAL merge as primary, manual reassembly as fallback
tags: [adr, wal, sqlite]
status: accepted
date: 2026-07-04
---

# ADR-001: Native-WAL merge as primary, manual reassembly as fallback

## Context

WhatsApp Desktop v2.3000+ keeps most rows exclusively in the WAL file and never checkpoints into the main `.db` page store. Any tool that reads only the main DB gets an empty or ancient view.

Two strategies exist:

1. **Native WAL:** copy `.db`, `.db-wal`, and `.db-shm` to a temp dir and open with `sqlite3.connect`. SQLite's own WAL reader applies frames correctly.
2. **Manual reassembly:** parse WAL frames ourselves, write pages into the DB image, then open.

Manual reassembly is attractive because it's transparent and testable, but it drops subtle metadata SQLite's WAL reader would restore (page-1 header preservation, freelist maintenance, corruption tolerance). We observed subtle B-tree corruption in one test build when manual was primary.

## Decision

Native WAL is the primary strategy (`waren6.py:2019-2054`). Manual reassembly is the fallback (`waren6.py:2055+`), used only when the native path fails a schema sanity check against a known table.

## Consequences

- Requires copying up to three files to a temp dir per DB — an extra I/O pass.
- Requires cleanup of the temp dir after the caller closes the connection.
- Manual fallback still exists and is exercised by tests — cannot be removed.
- Behaviour is identical to what DB Browser produces, which matches operator expectations.

## Alternatives considered

- **Checkpoint before extraction:** would mutate evidence, unacceptable.
- **Only manual reassembly:** simpler, but risks silent corruption on new WhatsApp builds.
- **Only native WAL:** doesn't work on Python/SQLite builds that reject the WAL for checksum reasons.

## References

- `waren6.py:1993-2200` — `_apply_wal_and_open`
- [[Mistakes-not-to-repeat#1]]
