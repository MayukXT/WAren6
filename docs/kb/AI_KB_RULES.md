---
title: AI Knowledge-Base rules
tags: [meta, rules]
---

# AI_KB_RULES

Rules the AI agent must follow when working in this repo.

## Before starting

1. Read [[Home]] and skim [[Architecture]].
2. Read [[Mistakes-not-to-repeat]] before proposing any change to acquisition, decryption, WAL handling, or Store 8 crypto.
3. If the change touches performance-sensitive code, read [[perf/Bottlenecks]] first — the yardstick is any modest field-kit box (older laptops, low-power evidence machines), not a modern workstation.
4. If the change touches WhatsApp Desktop paths, package IDs, or IndexedDB layout, read [[compat/WhatsApp-version-compat]].

## While working

- Prefer editing existing files over adding new modules — the codebase is intentionally flat.
- When adding a non-trivial design decision, write an ADR in `adr/ADR-NNN-short-title.md`. Keep it short: context, decision, consequences, alternatives.
- When removing a feature or replacing an approach, append an entry to [[Deprecation-log]].
- When discovering a footgun that cost real time, append to [[Mistakes-not-to-repeat]] with the shortest reproduction.

## After finishing

- Run `graphify update .` (or the equivalent `python -m graphify.update` path used in this repo) so `graphify-out/graph.json` reflects the new structure.
- If you changed a file's public surface (new function, removed function, moved responsibility), update [[Architecture]].
- Never mark work done if tests fail. `python -m unittest discover -s tests -p 'test*.py'` is authoritative.

## What NOT to write here

- Ephemeral chat context. This vault is not a conversation log.
- Rewriting information already in `README.md` or `LLM.txt`. Cross-link instead.
- Anything that would become misleading if a file is renamed. Prefer semantics over hard file paths where possible; when a path IS important, note the commit SHA at write time.
