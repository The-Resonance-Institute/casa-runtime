# CASA Diligence Index

This document maps every material claim in the CASA repository to its evidence tier.

It exists for one purpose: when a technical reader encounters a claim and asks "where is the proof," this document answers that question with precision.

---

## Evidence Tiers

**Tier 1 — In this repository.** Public. No request required.  
**Tier 2 — Pre-NDA. Available on request.** Contact chrisherndonsr@gmail.com.  
**Tier 3 — Post-NDA.** Full technical package after NDA execution.

---

## Architecture Claims

| Claim | Evidence | Tier |
|-------|----------|------|
| Gate evaluates nine enumerated metadata fields (CAV) | [`CANONICAL_ACTION_VECTOR.md`](CANONICAL_ACTION_VECTOR.md) — full field specification with derivation rules | 1 |
| End-to-end latency 53–78ms | Component timing breakdown in [`ARCHITECTURE.md`](ARCHITECTURE.md) | 1 |
| Zero GPU, zero model weights, commodity compute | Architecture doc; gate engine source code | 1 / 3 |
| 93 constitutional primitives, 279 directed edges | Architecture doc (structure); full registry with weights and edges | 1 / 3 |
| Three-verdict resolution: ACCEPT / GOVERN / REFUSE | [`ARCHITECTURE.md`](ARCHITECTURE.md), [`TRACE_FORMAT.md`](TRACE_FORMAT.md), SDK interface | 1 |
| Hard-stop primitives force unconditional REFUSE | Architecture doc (mechanism described); registry with hard-stop nodes | 1 / 3 |
| Deterministic SHA-256 trace hash | [`TRACE_FORMAT.md`](TRACE_FORMAT.md) — hash computation specified | 1 |
| 100% trace coverage (not sampled) | Enforcement invariants; harness run logs | 1 / 2 |
| Fail-closed invariant (errors → REFUSE) | Enforcement invariants in [`ARCHITECTURE.md`](ARCHITECTURE.md) | 1 |
| Same input → same verdict, reproducible across environments | Determinism invariant; cross-platform harness run logs | 1 / 2 |

---

## Validation Claims

### Project Polis

| Claim | Evidence | Tier |
|-------|----------|------|
| 573 total governance evaluations | [`validation/polis_summary.md`](validation/polis_summary.md) | 1 |
| 0 false positives | Polis summary | 1 |
| 0 bypasses | Polis summary | 1 |
| 0 unprincipled divergences | Polis summary | 1 |
| 6 adversarial archetypes enumerated | Polis summary | 1 |
| Divergence score 0.1070 | Polis summary | 1 |
| 414.6 seconds continuous uptime | Polis summary | 1 |
| Full agent roster, per-evaluation trace corpus | — | 3 |
| Complete simulation methodology | — | 3 |

### CASA-FIN

| Claim | Evidence | Tier |
|-------|----------|------|
| 97% procyclical feedback loop reduction | [`validation/casa_fin_summary.md`](validation/casa_fin_summary.md) | 1 |
| System failure at Turn 4 without CASA | CASA-FIN summary | 1 |
| −81% forced asset sales with CASA | CASA-FIN summary | 1 |
| Wholesale funding preserved | CASA-FIN summary | 1 |
| 0 lawful actions suppressed | CASA-FIN summary | 1 |
| Turn-by-turn trace corpus (14-day simulation) | — | 3 |
| Domain module configuration schema (CASA-FIN) | — | 3 |
| Full simulation methodology | — | 3 |

### Project Meridian

| Claim | Evidence | Tier |
|-------|----------|------|
| REFUSE neg_ratio 0.1924 — identical across Claude and Gemini | [`validation/meridian_summary.md`](validation/meridian_summary.md) | 1 |
| Claude: 55% hostile actions in baseline | Meridian summary | 1 |
| Gemini: 15.5% hostile actions in baseline | Meridian summary | 1 |
| 100% hostile action governance across both models | Meridian summary | 1 |
| Full scenario configuration and agent roster | — | 3 |
| Raw trace corpus | — | 3 |

### Cross-Model Validation

| Claim | Evidence | Tier |
|-------|----------|------|
| 0 unprincipled divergences across 156 decisions | [`validation/cross_model_summary.md`](validation/cross_model_summary.md) | 1 |
| 100% trace generation across all three models | Cross-model summary | 1 |
| Claude: 71.2% match rate | Cross-model summary | 1 |
| Gemini: 57.7% match rate | Cross-model summary | 1 |
| GPT-4: 53.8% match rate | Cross-model summary | 1 |
| All red team attack classes governed | Cross-model summary | 1 |
| Full 52-prompt corpus with expected verdicts | — | 3 |
| Per-model response traces | — | 3 |
| Harness source code (v3.2.1) | — | 3 |

---

## IP Claims

| Claim | Evidence | Tier |
|-------|----------|------|
| Provisional patent filed February 2026 | USPTO Payment Receipt (Application #63/987,813) | 2 |
| 34-page patent specification covering architecture and 10 alternative embodiments | Full specification | 2 |
| Primitives derived from 12-volume, ~1M word philosophical corpus | Described in architecture docs; corpus itself | 1 / 3 |
| 93 semantic cards (canonical definitions, exemplars, confusables) | — | 3 |
| Constitutional registry locked at v1.0.0 | Registry JSON with full primitive definitions, weights, edge topology | 3 |

---

## Pre-NDA Package (Available on Request)

The following are available without NDA execution for qualified technical contacts:

- USPTO payment receipt (patent filing evidence)
- Two published SSRN papers (Constitutional Drift; CASA Architecture)
- Pre-NDA Technical Overview v3.0
- Executive Memo (The Missing Control Plane)
- Cross-model validation summary report
- Enterprise simulation dashboard (also in this repo)

Contact: **chrisherndonsr@gmail.com**

---

## Post-NDA Technical Package

The full diligence package includes:

- Complete 93-primitive constitutional registry (JSON, locked v1.0.0)
- 93 semantic cards (YAML, full primitive ontology)
- Vector-to-Primitive Activation Engine rule set
- Propagation constants and calibration methodology
- Gate engine source code (Python, v4.0.0)
- Sovereign enforcement layer and contract system
- Cross-model validation harness (v3.2.1) with locked prompt registry
- Full trace corpora: Polis (573 traces), Meridian, CASA-FIN
- Domain module configuration schemas (FIN, HIPAA, ITAR, LEGAL, FERPA)
- EU AI Act compliance mapping
- 26-test hostile diligence suite with invariant verification
- 12-volume canonical substrate (the philosophical foundation)

---

## Contact

**Christopher T. Herndon**  
Founder, The Resonance Institute, LLC  
chrisherndonsr@gmail.com · 949-745-1607

*USPTO Application #63/987,813 — Filed February 2026*  
*© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC*
