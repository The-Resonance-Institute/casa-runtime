# CASA
**Constitutional AI Safety Architecture**

Deterministic pre-execution governance for agent actions and API calls. → [Live Governance Simulation](https://the-resonance-institute.github.io/casa-runtime)

![Patent](https://img.shields.io/badge/USPTO-Provisional%20%2363%2F987%2C813-blue) ![Validation](https://img.shields.io/badge/Validation-License-green)

---

## Live Gate

The CASA gate is deployed and accepting requests now.

| Endpoint | URL |
|---|---|
| Health | https://casa-gate.onrender.com/health |
| Interactive API | https://casa-gate.onrender.com/docs |
| Evaluate | POST https://casa-gate.onrender.com/evaluate |

**Try it in 30 seconds — no setup, no code, no API key:**
Go to https://casa-gate.onrender.com/docs, open POST /evaluate, click Try it out, paste the example below, click Execute.

```json
{
  "action_class": "MANIPULATE",
  "target_type": "INSTITUTION",
  "content": "Transfer funds without LP approval",
  "agent_name": "Finance-Agent"
}
```

You will get back a real verdict, a real trace hash, and a real latency. Not a simulation.

---

CASA is a deterministic admissibility gate placed in front of execution systems.

It evaluates structured action requests before execution and returns one of three outcomes:

```
ACCEPT    →  Execution proceeds
GOVERN    →  Execution proceeds with binding structural constraints
REFUSE    →  Execution blocked. No downstream system is invoked.
```

CASA does not interpret natural language.
CASA does not use embeddings or classification models.
CASA operates on structured action vectors.

---

## What It Looks Like

An agent proposes a financial transfer. Before anything executes, CASA evaluates the request:

**Input — Canonical Action Vector**

```json
{
  "actor_class":   "AGENT",
  "action_class":  "TRANSFER",
  "target_class":  "RESOURCE",
  "scope":         "SINGLE",
  "magnitude":     "MATERIAL",
  "authorization": "AT_LIMIT",
  "timing":        "ROUTINE",
  "consent":       "EXPLICIT",
  "reversibility": "COSTLY"
}
```

**Output — Gate verdict with audit trace**

```json
{
  "verdict": "GOVERN",
  "trace_id": "a3f9c2d1-...",
  "trace_hash": "31006d0784738d49",
  "constraints": [
    { "type": "FIELD_REQUIRED", "target": "approval_token", "source_primitive": "CP009" },
    { "type": "DISCLOSURE",     "target": "audit_log",      "source_primitive": "CP005" }
  ],
  "resolution": {
    "pos_mass": 3.847,
    "neg_mass": 0.412,
    "neg_ratio": 0.0968,
    "verdict": "GOVERN"
  }
}
```

Same input. Same verdict. Same hash. Every time. Across any model.

---

## What CASA Is Not

This distinction matters because most AI safety tools operate at the content layer.

CASA does not moderate text
CASA does not interpret prompts
CASA does not classify language
CASA does not supervise model outputs
CASA does not call a secondary model
CASA does not use GPU or model weights

**CASA governs execution requests — not content.**

The natural language payload of a request is opaque to the gate. An adversary who poisons the prompt, rewrites the instruction, or jailbreaks the model still faces the gate. The gate never read the text.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    EXECUTION SOURCES                      │
│                                                           │
│  LLM Tool Call  │  Human API  │  Webhook  │  Cron Job    │
│  RPA Action     │  Agent Msg  │  Service  │  External    │
└─────────────────────────┬────────────────────────────────┘
                          │  structured request
                          ▼
┌──────────────────────────────────────────────────────────┐
│                       CASA GATE                           │
│                                                           │
│  1. CAV Mapper          derives 9-field vector            │
│     (no content read)   from request metadata             │
│                                                           │
│  2. Activation Engine   deterministic lookup tables       │
│     (VPAE)              → primitive activations           │
│                                                           │
│  3. Constitutional      93-primitive graph                │
│     Graph Propagation   279 directed edges                │
│                         Decimal arithmetic                │
│                         fixed iteration order             │
│                                                           │
│  4. Verdict Resolution  pos_mass / neg_mass ratio         │
│                         hard-stop overrides               │
│                         threshold bands                   │
│                                                           │
│  5. CASA-T1 Trace       SHA-256 hash                      │
│                         100% trace coverage               │
│                         tamper-evident                    │
└───────────┬──────────────────────────┬───────────────────┘
            │                          │
     ACCEPT / GOVERN               REFUSE
            │                          │
            ▼                          ▼
   ┌─────────────────┐       ┌──────────────────┐
   │  Downstream     │       │  Blocked.         │
   │  System         │       │  No call made.    │
   │  (invoked)      │       │  Trace only.      │
   └─────────────────┘       └──────────────────┘
```

End-to-end latency: 53–78ms. No GPU. No model calls. Commodity compute.

---

## Quick Integration

```python
from casa_client import CASAClient, CanonicalActionVector
from casa_client import ActorClass, ActionClass, TargetClass
from casa_client import Scope, Magnitude, Authorization
from casa_client import Timing, Consent, Reversibility, Verdict

client = CASAClient(gate_url="https://casa-gate.onrender.com", api_key="your-key")

result = client.evaluate(CanonicalActionVector(
    actor_class   = ActorClass.AGENT,
    action_class  = ActionClass.DELETE,
    target_class  = TargetClass.DATA,
    scope         = Scope.BOUNDED,
    magnitude     = Magnitude.MATERIAL,
    authorization = Authorization.WITHIN_GRANT,
    timing        = Timing.ROUTINE,
    consent       = Consent.EXPLICIT,
    reversibility = Reversibility.REVERSIBLE,
))

if result.verdict == Verdict.REFUSE:
    raise ExecutionBlocked(result.trace_id)

if result.verdict == Verdict.GOVERN:
    apply_constraints(result.constraints)

proceed()
```

See `sdk/python/casa_client.py` for the full typed interface. See `docs/integration.md` for gateway, sidecar, and agent runtime patterns.

This repository exposes the public interface, integration patterns, and validation layer. Enterprise runtime materials are available separately under NDA.

---

## Source Agnosticism

CASA governs any structured execution request regardless of origin:

- LLM tool calls and function calls
- Human-initiated REST / GraphQL / RPC calls
- Scheduled jobs (cron, task queues, batch pipelines)
- Webhook-triggered workflows
- Robotic process automation actions
- Agent-to-agent messages in multi-agent orchestrations

The Canonical Action Vector abstracts away the source. The same nine fields are derived whether the request comes from a model, a human, or an automated process. Execution source selection becomes a capability and cost decision — not a governance decision.

---

## Validation

CASA has been validated across four distinct proof scenarios.

### Project Polis — Multi-Agent Adversarial Enforcement

20 agents. 14 cooperative. 6 adversarial archetypes: power accumulator, coalition builder, procedural saboteur, reputation assassin, forum troll, narrative controller.

| Metric | Result |
|---|---|
| Total governance evaluations | 573 |
| False positives | 0 |
| Bypasses | 0 |
| Unprincipled divergences | 0 |

→ Full summary

### CASA-FIN — Regulated Financial Stress

10 rational agents. Regional bank stress scenario. No agent was malicious. The failure mode was execution simultaneity — individually lawful actions combining into system collapse.

| Metric | Without CASA | With CASA |
|---|---|---|
| System failure | Turn 4 | Survived |
| Procyclical feedback loops | 30 | 1 |
| Forced asset sales | Baseline | −81% |

→ Full summary

### Project Meridian — Cross-Model Sovereignty

Same scenario. Two frontier models (Claude Sonnet 4, Gemini 2.5 Pro). Radically different behavioral profiles in baseline. REFUSE neg_ratio across both: 0.1924 — identical. Swap the model. The verdicts hold.

→ Full summary

### Cross-Model Validation — Three Providers

52 prompts. 156 governed decisions. Zero unprincipled divergences across Claude, GPT-4, and Gemini.

→ Full summary

Full proof scenario data — trace corpora, harness source, simulation methodology — is available under NDA. See `DILIGENCE.md` for the complete claim-to-evidence map.

---

## Economic Reality

At 1M agent actions per day:

| Approach | Daily Cost | Latency | Deterministic | Auditable |
|---|---|---|---|---|
| LLM-as-judge | $1,000–$10,000 | 5–15s | ✗ | ✗ |
| Safety classifier | $100–$1,000 | 200–500ms | ✗ | ✗ |
| CASA | Commodity compute | 53–78ms | ✓ | ✓ |

---

## Enforcement Invariants

| Invariant | Guarantee |
|---|---|
| REFUSE | verdict == REFUSE → no downstream system invoked. Unconditional. |
| Single-call | At most one downstream call. No retry loops. No fallbacks. |
| Determinism | Same input + same config → same verdict + same trace + same hash. Always. |
| Fail-closed | Errors → REFUSE. Missing fields → GOVERN. |
| Sovereignty | No external actor can override a REFUSE verdict. |
| Completeness | 100% of evaluations traced. Not sampled. |

---

## Repository Contents

| Path | Contents |
|---|---|
| `ARCHITECTURE.md` | Full control plane architecture and evaluation pipeline |
| `CANONICAL_ACTION_VECTOR.md` | Nine-field CAV specification with derivation rules and examples |
| `TRACE_FORMAT.md` | CASA-T1 audit trace schema |
| `docs/integration.md` | Integration patterns: gateway, sidecar, agent runtime, embedded |
| `sdk/python/casa_client.py` | Typed Python client showing the full call contract |
| `examples/enterprise_dashboard/` | Live dashboard: 10 agents, 26 tools, 45 evaluations — open in browser |
| `validation/` | Proof scenario summaries |

---

## Why This Matters

Modern AI systems are moving from conversational interfaces to autonomous tool-using agents. The critical safety problem is no longer what models say. It is what they are allowed to execute.

Current architectures have a data plane — model inference, API processing, job execution. There is no control plane. CASA is the control plane.

---

## Status

CASA is production-ready governance infrastructure. The architecture has been validated through multiple simulation environments and cross-model testing. A provisional patent covering the core architecture has been filed.

| Component | Status |
|---|---|
| USPTO Provisional Patent | Filed February 2026 — #63/987,813 |
| Gate Engine | Production v4.0.0 |
| Live Gate Endpoint | https://casa-gate.onrender.com |
| Constitutional Registry | Locked v1.0.0 (93 primitives, 279 edges) |
| Cross-Model Validation | Complete — Claude, GPT-4, Gemini |
| Project Polis | Complete — 573 evaluations |
| CASA-FIN | Complete |
| Domain Modules | CASA-FIN validated; HIPAA, ITAR, LEGAL, FERPA in specification |

For a complete map of every claim in this repository to its evidence tier — what is public, what is pre-NDA, and what is post-NDA — see `DILIGENCE.md`.

---

Inquiries regarding research collaboration, enterprise evaluation, or commercial licensing:

**Christopher T. Herndon · Founder, The Resonance Institute, LLC**
contact@resonanceinstitutellc.com

Pre-NDA materials available immediately. Full technical package under NDA.

---

*© 2025–2026 Christopher T. Herndon / The Resonance Institute, LLC*
*USPTO Provisional Application #63/987,813*
