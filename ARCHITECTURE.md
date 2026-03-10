# CASA Architecture Overview

**Deterministic Pre-Execution Control Plane for Structured Execution Environments**  
*Gate Engine v4.0.0 | Registry v1.0.0*

---

## The Problem This Solves

Execution environments have a data plane (model inference, API processing, job execution) but no control plane (execution governance). Current approaches attempt to solve this at the wrong layer:

| Approach | What It Evaluates | When | Cost | Deterministic |
|----------|------------------|------|------|---------------|
| LLM-as-judge | Output content | Post-generation | $1k–$10k/day at scale | No |
| Safety classifier | Output content | Post-generation | $100–$1k/day at scale | No |
| Prompt guardrails | Model input | Pre-generation | No enforcement authority | No |
| Policy engine | Request rules | Pre-execution | Low | Yes, but no constitutional substrate |
| **CASA** | **Request metadata** | **Pre-execution** | **Commodity compute** | **Yes** |

CASA is not in competition with any of these. It operates at the control plane, below the content layer. It governs *execution admissibility*, not *output content*.

---

## System Boundaries

```
                    ┌─────────────────────────────────┐
                    │        EXECUTION SOURCES         │
                    │                                  │
                    │  LLM Tool Call  │  Human API     │
                    │  Scheduled Job  │  Webhook        │
                    │  RPA Action     │  Agent Message  │
                    └────────────────┬────────────────-┘
                                     │ structured request
                                     ▼
                    ┌─────────────────────────────────┐
                    │         CASA GATE               │
                    │                                 │
                    │  1. CAV Mapper                  │
                    │  2. Activation Engine (VPAE)    │
                    │  3. Constitutional Graph        │
                    │  4. Verdict Resolution          │
                    │  5. CASA-T1 Trace               │
                    └──────────┬────────────┬─────────┘
                               │            │
                   ACCEPT /    │            │  REFUSE
                   GOVERN      ▼            ▼
                    ┌──────────────┐  ┌──────────────┐
                    │  Downstream  │  │   Blocked.   │
                    │  System      │  │   No call.   │
                    │  (invoked)   │  │   Trace only.│
                    └──────────────┘  └──────────────┘
```

---

## Component Architecture

### 1. Canonical Action Vector Mapper

Transforms a raw structured request into the nine-field CAV.

The mapper consults:
- **Endpoint/tool registry** — maps endpoint or tool identifier to `action_class` and `target_class`
- **Authentication context** — derives `actor_class` from caller identity
- **Resource schema** — determines `target_class` from resource type
- **Domain thresholds** — computes `magnitude` against configured significance levels
- **Role grants** — computes `authorization` by comparing caller grants against required permissions
- **SLA metadata** — derives `timing` from queue priority and processing flags
- **Approval token chain** — derives `consent` from workflow state and delegation records
- **Resource property metadata** — derives `reversibility` from deletion type and side effect flags

No field requires content interpretation. No field involves probabilistic inference. No secondary model is called.

### 2. Vector-to-Primitive Activation Engine (VPAE)

Maps the CAV to initial primitive activations.

The activation rules are pre-configured lookup tables: deterministic pattern matches that map vector field combinations to primitive activations at fixed weights. Rules are evaluated in fixed order. All matching rules fire. There is no short-circuit evaluation.

This is dictionary matching, not semantic interpretation.

### 3. Constitutional Graph Propagation

Spreads activation through the 93-primitive constitutional graph.

The graph has 279 directed edges: 123 operative (weight 0.6) and 156 interpretive (weight 0.4). Propagation uses fixed-precision Decimal arithmetic (no floating-point drift). Iteration order is fixed by sorted primitive identifiers. Edge traversal order is fixed by sorted (source, target, edge_type) tuples.

The graph runs up to 10 iterations with a convergence threshold of 0.001.

### 4. Verdict Resolution Engine

Partitions the activated primitive set by polarity.

- Excitatory activations sum to `pos_mass`
- Inhibitory activations sum to `neg_mass`
- `neg_ratio = neg_mass / (neg_mass + pos_mass)`

**Hard-stop check:** Three primitives in the Collapse family can force REFUSE when activated above threshold, regardless of the mass ratio. This is an unconditional override.

**Threshold bands:**
- `neg_ratio < 0.10` → ACCEPT
- `0.10 ≤ neg_ratio < 0.85` → GOVERN
- `neg_ratio ≥ 0.85` → REFUSE

(Thresholds are configurable per deployment and recorded in the config_hash.)

### 5. CASA-T1 Trace Generator

Emits the complete audit record for every evaluation.

The trace includes: derived CAV, every primitive that activated with its weight, the complete propagation path, mass computation, verdict, constraints (for GOVERN), and a deterministic SHA-256 hash. See [TRACE_FORMAT.md](TRACE_FORMAT.md) for full schema.

---

## The 93-Primitive Constitutional Graph

The constitutional primitive graph is the core proprietary IP of CASA.

93 primitives. 279 directed dependency edges. Three tiers:

- **Foundational (30):** Core ontological structures. Axiomatic nodes with no operative dependencies.
- **Structural (43):** Patterns built on foundational concepts.
- **Behavioral (20):** Observable governance outcomes. Includes the three Collapse hard-stop nodes.

Six primitives carry inhibitory polarity (contributing to neg_mass). Three of these are hard-stop nodes that force REFUSE when activated above threshold.

The primitives are structurally derived from a 12-volume, approximately one million word philosophical corpus on governance, leadership, and institutional continuity developed over a decade. The graph topology alone — without access to the derivation corpus and calibration methodology — does not reconstruct the primitive definitions or the reasoning behind the edge weights.

**The primitive registry, semantic cards, activation rules, and propagation constants are available under NDA.**

---

## Enforcement Invariants

These properties hold for every evaluation, every configuration, every deployment. Violation of any invariant constitutes a system defect.

```
REFUSE invariant:        verdict == REFUSE  →  backend_called == false
Single-call invariant:   downstream_calls ≤ 1 (no retry, no fallback)
Determinism invariant:   same_input + same_config  →  same_verdict + same_trace + same_hash
Fail-closed invariant:   errors → REFUSE | missing fields → GOVERN
Sovereignty invariant:   no external actor can override a REFUSE verdict
Completeness invariant:  every evaluation produces a trace (100%, not sampled)
```

---

## Integration Patterns

### Gateway
```
Client → [CASA Gate] → Downstream API
```
Inserted as reverse proxy or middleware. No changes to downstream systems.

### Sidecar
```
Application → CASA.evaluate(vector) → act on verdict → Downstream
```
Application retains control; consults gate before each execution.

### Agent Runtime
```
Agent.propose_action() → Orchestrator → [CASA Gate] → execute or block
```
Works with any framework that separates action proposal from execution (LangChain, AutoGen, CrewAI, custom orchestrators).

### Embedded Library
```
[Application + CASA library] → in-process evaluation → Downstream
```
Sub-millisecond path. No network call. Suitable for high-throughput environments.

---

## Performance

| Component | Latency |
|-----------|---------|
| CAV derivation | 5–10ms |
| Activation engine | 1–5ms |
| Graph propagation | 30–50ms |
| Verdict resolution | 1–5ms |
| Trace generation | 5–10ms |
| **End-to-end** | **53–78ms average** |

**No GPU. No model weights. No inference overhead.**  
Memory footprint: ~500KB for primitive registry + ~50KB per-request state.  
Horizontally scalable: consistent verdicts across instances due to deterministic evaluation.

---

## Domain Modules

The core gate is unchanged across all domains. Domain modules configure:
- Magnitude thresholds (what counts as TRIVIAL / MATERIAL / CRITICAL in this domain)
- Authorization rules (role → permission mapping)
- Consent requirements (what actions require explicit approval)
- Reversibility properties (what actions are irreversible in this domain)
- Additional activation rules (additive to core; do not override)
- Constraint schemas (what constraints attach to GOVERN verdicts)

| Module | Domain | Status |
|--------|--------|--------|
| CASA-FIN | Financial services | Validated |
| CASA-HIPAA | Healthcare | Specification complete |
| CASA-ITAR | Defense / export control | Specification complete |
| CASA-LEGAL | Legal services | Specification complete |
| CASA-FERPA | Education | Specification complete |

---

*© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC*  
*Provisional patent filed USPTO Application #63/987,813*
