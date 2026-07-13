---
title: WAren6 Knowledge Base
tags: [home, index]
---

# WAren6 Knowledge Base

WAren6 = **W**hats**A**pp + Fo**ren**sics(**6**). Windows toolkit for WhatsApp Desktop forensic extraction, unification, and review.

This vault is the persistent memory for improvements, decisions, and gotchas. Keep it updated when the architecture changes or when a subtle behavior costs somebody an hour.

## Top-level artefacts

- Field Kit orchestrator: [[Architecture#waren6.ps1]] — `waren6.ps1` (4858 lines)
- Unifier / reports: [[Architecture#waren6.py]] — `waren6.py` (4885 lines)
- Case preparation: `waren6_unify_case.py` (~122 lines)
- Live runtime supplement: `tools/wa_live_runtime_capture.js`
- Reader (separate release): `waren6-reader/` (Tauri app)
- AI reference: `LLM.txt`

## Sections

- [[Architecture]] — overall pipeline map
- [[perf/Bottlenecks]] — ranked hot paths for slower/older field-kit hardware
- [[compat/WhatsApp-version-compat]] — version-fragile assumptions
- [[Mistakes-not-to-repeat]] — known footguns from past debugging
- [[Deprecation-log]] — removed features, why, replaced by
- [[NOTES]] — running scratchpad
- [[AI_KB_RULES]] — how the AI agent should use this vault
- ADRs: `adr/`
- Research: `research/`

## Graphify

- Code graph: `graphify-out/graph.json` (1041 nodes, 2522 edges, 53 communities)
- Report: `graphify-out/GRAPH_REPORT.md`
- Query the graph: `graphify query "<question>"`
- Rebuild after refactor: `graphify update .`

## Fast pointers

| Question | See |
|---|---|
| Why is extraction slow on modest hardware? | [[perf/Bottlenecks]] |
| Does this still work on newest WhatsApp? | [[compat/WhatsApp-version-compat]] |
| How is Store 8 handled? | [[adr/ADR-002-store8-hybrid-recovery]] |
| Why native WAL not manual? | [[adr/ADR-001-native-wal-merge]] |
| What did we already try? | [[Mistakes-not-to-repeat]] |
| Why split acquire on target from unify on workstation? | [[adr/ADR-003-split-machine-workflow]] |
| How does client-key recovery survive schema changes? | [[adr/ADR-004-session-key-schema-agnostic]] |
| How do I get real per-stage timings? | Run `python waren6.py --unify <case> --profile`; see `unify_profile.json` |
