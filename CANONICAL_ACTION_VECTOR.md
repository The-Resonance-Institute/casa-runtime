# Canonical Action Vector — Field Specification

The Canonical Action Vector (CAV) is the sole input to the CASA gate.

It reduces any structured execution request to nine enumerated metadata fields.  
No natural language is parsed. No content is read. No probabilistic inference occurs.  
Every field is derived deterministically from request metadata.

---

## The Nine Fields

### `actor_class`
**Who is requesting.**  
Derived from authentication context and caller identity.

| Value | Description |
|-------|-------------|
| `HUMAN` | User session, OAuth token, human-initiated API call |
| `AGENT` | LLM tool call, autonomous agent action |
| `SERVICE` | Internal service-to-service call |
| `SCHEDULED` | Cron job, task queue, batch pipeline |
| `EXTERNAL` | Webhook, third-party integration, inbound event |

---

### `action_class`
**What the request asks to do.**  
Looked up from the endpoint/tool registry using the endpoint or tool identifier. Pre-registered at deployment, not inferred at runtime.

| Value | Description |
|-------|-------------|
| `QUERY` | Read-only data retrieval |
| `CREATE` | New resource or record creation |
| `MODIFY` | Update to existing resource |
| `DELETE` | Removal of resource or record |
| `TRANSFER` | Movement of value, data, or authority |
| `EXECUTE` | Running code, scripts, or workflows |
| `ESCALATE` | Elevation of permission or authority |

---

### `target_class`
**What the request acts upon.**  
Looked up from the resource schema using the target resource type.

| Value | Description |
|-------|-------------|
| `SELF` | The requesting actor's own state |
| `DATA` | Records, files, configurations |
| `RESOURCE` | Infrastructure, services, capacity |
| `PRINCIPAL` | User accounts, identity records |
| `GROUP` | Collections of principals or resources |
| `SYSTEM` | Platform-level or architectural targets |

---

### `scope`
**Blast radius of the request.**  
Computed from request parameters by counting affected entities or evaluating query predicate boundedness.

| Value | Description |
|-------|-------------|
| `SINGLE` | One record or entity |
| `BOUNDED` | Explicitly scoped subset (e.g., date range, department) |
| `UNBOUNDED` | No explicit limit; potentially affects all matching records |

---

### `magnitude`
**Organizational significance.**  
Computed from request parameters against configured domain thresholds. Thresholds are domain-specific (a $10K financial transaction threshold differs from a healthcare PHI threshold).

| Value | Description |
|-------|-------------|
| `TRIVIAL` | Below significance threshold for this domain |
| `MATERIAL` | Above significance threshold, below critical |
| `CRITICAL` | At or above critical threshold for this domain |

---

### `authorization`
**Relationship between request and caller's granted permissions.**  
Computed by comparing caller's role grants against required permissions for the action on the target.

| Value | Description |
|-------|-------------|
| `WITHIN_GRANT` | Caller's role explicitly includes this action/target combination |
| `AT_LIMIT` | Caller is at the boundary of granted permissions |
| `EXCEEDS_GRANT` | Caller's role does not include this action/target combination |

---

### `timing`
**Urgency context.**  
Derived from SLA metadata, queue priority, and processing flags.

| Value | Description |
|-------|-------------|
| `ROUTINE` | Standard processing window |
| `EXPEDITED` | Priority queue, elevated urgency |
| `IMMEDIATE` | Real-time, synchronous execution required |

---

### `consent`
**Whether affected principals have approved the action.**  
Derived from approval token chain, workflow state, and delegation records.

| Value | Description |
|-------|-------------|
| `EXPLICIT` | Approval token present; affected principal(s) have specifically authorized this action |
| `IMPLIED` | Consent derivable from role assignment, policy, or prior agreement |
| `NONE` | No approval token; no derivable consent |

---

### `reversibility`
**Whether effects can be undone.**  
Derived from target resource's property metadata: deletion type, undo support, external side effects.

| Value | Description |
|-------|-------------|
| `REVERSIBLE` | Action can be undone (soft delete, backup exists, no external side effects) |
| `COSTLY` | Reversible but with significant overhead (audit required, data recovery window) |
| `IRREVERSIBLE` | Cannot be undone (hard delete, external propagation, wire transfer settled) |

---

## Vector Examples

### Example 1: AI agent deletes a customer record
Expected verdict: **GOVERN**

```json
{
  "actor_class":   "AGENT",
  "action_class":  "DELETE",
  "target_class":  "PRINCIPAL",
  "scope":         "SINGLE",
  "magnitude":     "MATERIAL",
  "authorization": "WITHIN_GRANT",
  "timing":        "ROUTINE",
  "consent":       "EXPLICIT",
  "reversibility": "COSTLY"
}
```
Material deletion of a principal record, even with authorization and consent, warrants audit trace and constraint emission.

---

### Example 2: Scheduled cron job purges expired session data
Expected verdict: **ACCEPT**

```json
{
  "actor_class":   "SCHEDULED",
  "action_class":  "DELETE",
  "target_class":  "DATA",
  "scope":         "BOUNDED",
  "magnitude":     "TRIVIAL",
  "authorization": "WITHIN_GRANT",
  "timing":        "ROUTINE",
  "consent":       "IMPLIED",
  "reversibility": "REVERSIBLE"
}
```
Routine, trivial, bounded, authorized, reversible housekeeping.

---

### Example 3: External webhook triggers unbounded system configuration change
Expected verdict: **REFUSE**

```json
{
  "actor_class":   "EXTERNAL",
  "action_class":  "MODIFY",
  "target_class":  "SYSTEM",
  "scope":         "UNBOUNDED",
  "magnitude":     "CRITICAL",
  "authorization": "EXCEEDS_GRANT",
  "timing":        "IMMEDIATE",
  "consent":       "NONE",
  "reversibility": "IRREVERSIBLE"
}
```
External source, exceeding authorization, modifying system configuration with unbounded scope, critical magnitude, no consent, irreversible consequences. Multiple hard-stop primitives activate.

---

### Example 4: Human operator queries financial report data
Expected verdict: **ACCEPT or GOVERN** (depends on data sensitivity configuration)

```json
{
  "actor_class":   "HUMAN",
  "action_class":  "QUERY",
  "target_class":  "DATA",
  "scope":         "BOUNDED",
  "magnitude":     "MATERIAL",
  "authorization": "WITHIN_GRANT",
  "timing":        "ROUTINE",
  "consent":       "IMPLIED",
  "reversibility": "REVERSIBLE"
}
```

---

## Derivation Architecture

Fields are not guessed or inferred from content. They are looked up from pre-configured registries:

- `action_class` — endpoint/tool registry, pre-registered at deployment
- `target_class` — resource schema
- `actor_class` — authentication context
- `scope` — request parameter analysis (entity count, predicate boundedness)
- `magnitude` — domain threshold configuration
- `authorization` — role grant comparison
- `timing` — SLA metadata and queue priority
- `consent` — approval token chain and delegation records
- `reversibility` — resource property metadata

**This is the integration work.** CASA requires that these mappings exist in your deployment configuration. Once the endpoint registry, resource schemas, and domain thresholds are configured, CAV derivation is fully automatic.

---

## Source Agnosticism

The same nine fields are derived whether the request originates from:
- An LLM tool call
- A human REST API call
- A scheduled cron job
- A webhook trigger
- An RPA action
- An agent-to-agent message

The gate does not care what generated the request. It cares what the request asks to do.

This means execution source selection becomes a pure capability and cost decision, not a governance decision.

---

*© 2025–2026 Christopher T. Herndon / The Resonance Institute, LLC*  
*Provisional patent filed USPTO Application #63/987,813*
