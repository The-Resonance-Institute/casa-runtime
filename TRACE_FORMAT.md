# CASA-T1 Audit Trace Format

Every CASA gate evaluation produces a complete, tamper-evident audit record (CASA-T1 v5.0).

100% of evaluations are traced. Not sampled.

---

## Trace Schema

```json
{
  "trace_version": "5.0",
  "trace_id": "uuid-v4",
  "timestamp": "ISO-8601",
  "gate_version": "4.0.0",
  "config_hash": "sha256-truncated-16-chars",

  "input": {
    "canonical_vector": {
      "actor_class": "AGENT",
      "action_class": "DELETE",
      "target_class": "PRINCIPAL",
      "scope": "SINGLE",
      "magnitude": "MATERIAL",
      "authorization": "WITHIN_GRANT",
      "timing": "ROUTINE",
      "consent": "EXPLICIT",
      "reversibility": "COSTLY"
    },
    "input_hash": "sha256-truncated-16-chars"
  },

  "recognition": {
    "rules_fired": ["rule_id_1", "rule_id_2"],
    "initial_activations": {
      "CP001": 0.4,
      "CP028": 0.3,
      "CP089": 0.0
    }
  },

  "propagation": {
    "edge_count": 279,
    "iterations": 4,
    "converged": true,
    "steps": [
      {
        "iteration": 1,
        "step_in_iteration": 1,
        "source_primitive": "CP001",
        "target_primitive": "CP012",
        "edge_type": "interpretive",
        "weight": 0.4,
        "source_activation": 0.4,
        "contribution": 0.136,
        "target_activation_before": 0.0,
        "target_activation_after": 0.136
      }
    ],
    "final_activations": {
      "CP001": 0.847,
      "CP012": 0.612,
      "CP089": 0.091
    }
  },

  "resolution": {
    "pos_mass": 3.847,
    "neg_mass": 0.412,
    "neg_ratio": 0.0968,
    "hard_stop_fired": false,
    "hard_stop_primitive": null,
    "verdict": "GOVERN"
  },

  "constraints": [
    {
      "type": "FIELD_REQUIRED",
      "target": "deletion_reason",
      "requirement": "Reason for deletion must be documented",
      "source_primitive": "CP007"
    },
    {
      "type": "DISCLOSURE",
      "target": "audit_log",
      "requirement": "Principal deletion must be recorded in audit log",
      "source_primitive": "CP005"
    }
  ],

  "trace_hash": "31006d0784738d49"
}
```

---

## Field Definitions

### Top Level

| Field | Description |
|-------|-------------|
| `trace_version` | Protocol version identifier |
| `trace_id` | UUID v4 unique identifier for this evaluation |
| `timestamp` | ISO-8601 timestamp of evaluation |
| `gate_version` | Gate software version |
| `config_hash` | SHA-256 of deployment configuration (truncated). Enables audit reconstruction of exact configuration at evaluation time. |

### Input

| Field | Description |
|-------|-------------|
| `canonical_vector` | The complete nine-field vector submitted for evaluation |
| `input_hash` | SHA-256 of the input vector (truncated) |

### Recognition

| Field | Description |
|-------|-------------|
| `rules_fired` | List of activation rule identifiers that matched the CAV |
| `initial_activations` | Primitive → initial weight mapping from the activation engine |

### Propagation

| Field | Description |
|-------|-------------|
| `edge_count` | Number of directed edges in the constitutional graph |
| `iterations` | Number of propagation iterations completed |
| `converged` | Whether convergence threshold was reached before max iterations |
| `steps` | Complete propagation path — every edge traversal recorded |
| `final_activations` | Final activation value for every primitive after propagation |

### Resolution

| Field | Description |
|-------|-------------|
| `pos_mass` | Sum of all excitatory primitive activations |
| `neg_mass` | Sum of all inhibitory primitive activations |
| `neg_ratio` | neg_mass / (neg_mass + pos_mass) |
| `hard_stop_fired` | Whether a hard-stop primitive forced REFUSE |
| `hard_stop_primitive` | The hard-stop primitive that fired, if any |
| `verdict` | ACCEPT, GOVERN, or REFUSE |

### Constraints

Populated for GOVERN verdicts only.

| Field | Description |
|-------|-------------|
| `type` | FIELD_REQUIRED, ENUM_RESTRICTION, SCHEMA_COMPLIANCE, TOKEN_BUDGET, or DISCLOSURE |
| `target` | Field name or schema path the constraint applies to |
| `requirement` | Human-readable description of the requirement |
| `source_primitive` | CP### — the primitive that triggered this constraint |

---

## Trace Integrity

The `trace_hash` is computed as the SHA-256 digest of the canonical JSON serialization of the complete trace content (excluding `trace_hash` itself), truncated to 16 hexadecimal characters.

**Any modification to any field in the trace changes the hash.**

This provides tamper evidence without requiring external verification infrastructure. The hash can be independently recomputed by any party with access to the trace content, enabling third-party audit verification.

---

## Verdict Semantics

**ACCEPT:** Execution proceeds without constraints. The gate emits a trace but imposes no restrictions on downstream execution.

**GOVERN:** Execution proceeds with binding structural constraints. The gate emits a constraint object specifying required fields, allowed enumeration values, structural schema requirements, maximum token budgets, and disclosure requirements. Post-execution validation checks structural compliance. Non-compliant output never reaches the caller and escalates to REFUSE.

**REFUSE:** Execution is blocked. The requested action never occurs. No downstream system is invoked. If `verdict == REFUSE`, then `backend_called == false`. This is unconditional and cannot be overridden.

---

## Regulatory Use

The CASA-T1 trace provides the audit artifact required for:

- **EU AI Act** — documented risk assessment, technical robustness evidence, human oversight documentation
- **SEC / FINRA** — cryptographically verifiable evidence that a specific governance evaluation occurred with a specific outcome, suitable for algorithmic decision audit
- **HIPAA** — complete access and modification audit trail for protected health information actions
- **Enterprise procurement** — demonstrable governance evidence for autonomous agent deployment in regulated contexts

Post-hoc logging cannot provide this. Probabilistic classifiers cannot provide this. Only a deterministic pre-execution gate with 100% trace coverage and cryptographic hash integrity can provide this.

---

*© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC*  
*Provisional patent filed USPTO Application #63/987,813*
