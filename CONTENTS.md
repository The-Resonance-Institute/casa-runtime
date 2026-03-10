# What Is and Isn't in This Repository

CASA is open-specification infrastructure. This repository contains the public specification, integration contract, and validation evidence.

The gate implementation is available under enterprise license and NDA.

---

## What's Here (Public)

```
casa-runtime/
├── README.md                       ← Start here
├── ARCHITECTURE.md                 ← Complete architectural overview
├── CANONICAL_ACTION_VECTOR.md      ← Nine-field CAV specification with examples
├── TRACE_FORMAT.md                 ← CASA-T1 audit trace schema
│
├── sdk/
│   ├── README.md                   ← Integration quickstart
│   └── python/
│       └── casa_client.py          ← Call contract + typed interfaces
│
├── examples/
│   └── enterprise_dashboard/
│       ├── index.html              ← Live dashboard: 1,000 agents, 10 departments
│       └── README.md
│
├── validation/
│   ├── polis_summary.md            ← 573 evaluations, 0 bypasses, 0 false positives
│   ├── casa_fin_summary.md         ← 97% cascade loop reduction in financial stress test
│   ├── meridian_summary.md         ← Source-invariant gate: same verdicts across models
│   └── cross_model_summary.md      ← Claude + GPT-4 + Gemini: 156 decisions, 0 U-DIV
│
└── docs/
    ├── ssrn_constitutional_drift.pdf   ← SSRN Paper 1
    └── ssrn_casa_architecture.pdf      ← SSRN Paper 2
```

---

## What's Available Under NDA

| Component | Description |
|-----------|-------------|
| 93-Primitive Constitutional Registry | Locked JSON — all primitives, weights, edge definitions, D-scores |
| Semantic Card System | 93 YAML cards with canonical definitions, exemplars, confusables, activation signatures |
| Vector-to-Primitive Activation Engine | Deterministic lookup tables — the activation rule set |
| Propagation Constants | The seven versioned constitutional constants |
| Gate Engine Source | Python implementation — CAV mapper, propagation engine, verdict resolution, trace generator |
| Domain Module Schemas | CASA-FIN (complete), CASA-HIPAA, CASA-ITAR, CASA-LEGAL, CASA-FERPA |
| Proof Scenario Data | Full trace corpora from Polis (573 traces), Meridian, CASA-FIN |
| Test Harness | Cross-model validation harness v3.2.1 with locked prompt registry |
| Patent Specification | Full 34-page provisional specification (USPTO #63/987,813) |

---

## Contact

**Christopher T. Herndon**  
Founder, The Resonance Institute, LLC  
chrisherndonsr@gmail.com · 949-745-1607

*Pre-NDA materials available immediately.*  
*Full technical package, diligence documentation, and EU AI Act compliance mapping available under NDA.*

---

*© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC*
