---
title: "ADR-003: Split-Machine Workflow -- acquire on target, unify on workstation"
tags: [adr, workflow, perf]
status: Accepted
date: 2026-07-07
---

# ADR-003: Split-Machine Workflow

## Status

Accepted (2026-07-07).

## Context

WAren6 acquisition targets are often modest hardware -- older laptops, low-power evidence PCs, Celeron/Atom-class field kits. Unification on these targets is CPU-heavy (Python Store 8 parse + fuzzy merge, HKDF+AES on opaque bodies, SQLite bulk writes, deferred index build, media SHA-256 hashing) and thermally throttles under sustained load, taking 25-40 minutes on a real 30k-message case.

Acquisition MUST run on the target -- DPAPI-NG keys are bound to the target user session and the ODUID. But unification is portable: the Python `--unify` code path reads already-decrypted `.dec.db` files, uses only stdlib + `cryptography` + `ccl_chromium_reader`, and contains no Windows-only imports (verified 2026-07 in the perf sprint).

## Decision

Officially recommend the split-machine workflow when target CPU is a concern:

1. **On target:** `waren6.ps1 -a` acquires and decrypts on target, packages `.tar.zst` archive with `.sha256.txt` + `.manifest.json` + `.logs.txt`. Skip `-m` (media indexing) and `--reports-dir` here.
2. **Transfer** archive to workstation. Verify SHA-256.
3. **On workstation:** `waren6.ps1 -u -c <case-path>` (Windows) or `python waren6.py --unify <case-path>` (Linux/macOS). Add `--with-media-index` and `--reports-dir` there.

Support this workflow with two additional flags landed in the same sprint:

- `--media-only <path-to-unified.db>` — run only media indexing against an existing unified DB. Enables deferring the ~30-120s SHA-256 pass off the target.
- `--profile` — per-stage timings written to `unify_profile.json`. Confirms the split is worth doing on this specific case.

## Consequences

**Positive:**

- 2-5x wall-clock reduction on modest-target cases.
- Less thermal throttling on target; unify runs on cores that don't downclock.
- Store 8 opaque body decryption (HKDF-heavy) naturally follows unify to workstation.
- Chain of custody preserved via `.sha256.txt` verification at each hop.

**Negative:**

- Requires archive transfer step (ops overhead; mitigated by existing `.tar.zst` packaging).
- Workstation needs Python 3.11+, `cryptography`, `ccl_chromium_reader`.
- If workstation is Linux/macOS, extraction needs `zstd -d` before `tar xf` (documented in LLM.txt).

## Alternatives Considered

1. **Unify on target with more parallelism.** Killed by:
   - `ccl_chromium_reader` has no locking; shared instance corrupts on shared file position, N independent instances re-decompress the same Snappy blocks.
   - Python GIL held during Snappy decompress and V8/Blink deserialize; threading doesn't help.
   - `ProcessPoolExecutor` on Windows uses spawn -- pickle costs + re-import overhead eats most of the win on dual-core.
2. **Do everything on workstation post-transfer of raw encrypted files.** Killed by DPAPI-NG binding to target user session -- session key material cannot be extracted off the target.
3. **Bundle a lighter unifier for target-only usage.** Would still be CPU-bound on the parse/merge phase; not a real solution.

## References

- `waren6.ps1:4230+` -- acquire path (Tier 1 / Tier 2 session key recovery landed in this sprint, see ADR-004).
- `waren6.ps1:4855+` (approx) -- unify-only branch (`-u -c <path>`).
- `waren6.py` -- `main()` `--unify` and `--media-only` dispatch.
- `LLM.txt` -- Split-Machine Workflow section, added this sprint.
- `docs/kb/perf/Bottlenecks.md` -- ranked bottleneck list.
- `docs/kb/adr/ADR-004-session-key-schema-agnostic.md` -- companion ADR for the key-recovery redesign that made this workflow viable on newer WA builds.
