---
title: ADR-002 — Hybrid Store 8 recovery (offline + optional live runtime)
tags: [adr, store8, crypto]
status: accepted
date: 2026-07-04
---

# ADR-002: Hybrid Store 8 recovery

## Context

WhatsApp Desktop's message store 8 in WebView2 IndexedDB stores newer messages as encrypted `msgRowOpaqueData` blobs. Decrypting them offline needs:

- Local HKDF **input key material** (IKM) — recoverable from IndexedDB artefacts.
- **Salt** — comes from the WebWA network path; not always present in local artefacts.
- **Info** parameter — small candidate set, easy to enumerate.

A pure-offline pipeline cannot always recover the salt. But a live logged-in WhatsApp Desktop already has the salt in memory. If we can ask it to serialise Store 8 rows for us, we side-step the salt-hunt entirely.

## Decision

Hybrid mode (default): offline extraction is authoritative; live runtime capture is a best-effort supplement.

- Offline path always runs and always produces a complete `unified_whatsapp.db` (rows are labeled `opaque_unresolved` when body cannot be recovered).
- Live path (via WebView2 DevTools + JS eval) captures Store 8 JSONL and is merged as `runtime_store8_records` in the unifier.
- If the offline row and the runtime row disagree on text, both are preserved with a `text_conflict_status` marker; the runtime version wins as the current-body candidate but the row keeps its provenance.

## Consequences

- Two independent recovery paths keep evidence visible even when one fails.
- Runtime path requires launching WhatsApp Desktop — visible or hidden. In headless CI or air-gapped forensic labs, `-f`/`--offline` must be used to skip it.
- Salt hunt (`waren6.py:1044-1142`) is a research-mode third option; not run by default. Only useful when both offline artefact enumeration and runtime capture fail.

## Alternatives considered

- **Runtime-only:** cannot run on air-gapped/collected evidence.
- **Offline-only:** loses recoverable bodies on newer WhatsApp builds where the salt lives only on the network.
- **Third-party decompilers of WA's JS bundle:** brittle, breaks on every WhatsApp release.

## References

- `waren6.py:600-911` — Store 8 crypto machinery
- `waren6.py:1044-1142` — salt hunt (opt-in via `--hunt-opaque-salt`)
- `waren6.ps1:3128-3288` — WebView2 DevTools runtime capture
- `tools/wa_live_runtime_capture.js` — the injected serialiser (also usable standalone from Node)
- [[Mistakes-not-to-repeat#4]]
