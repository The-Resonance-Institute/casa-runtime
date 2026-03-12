# CASA Integration Guide

How to place the CASA gate in front of your execution systems.

---

## The Integration Point

CASA inserts at exactly one point: **between the structured execution request and the downstream execution call.**

The integration requires no changes to the model, the tools, or the orchestration framework. You route the request through the gate, receive the verdict, and act on it.

---

## Pattern 0: Supported Frameworks — No CAV Construction Required

If you are using LangChain, OpenAI function calling, or CrewAI, skip Patterns 1–3.

The Universal Intake Adapter (UIA) handles CAV derivation automatically. Pass your native action format directly — the three-layer Constitutional Normalization Layer extracts fields, classifies action and target types via registry lookup, and resolves authority from agent role and spending limits without any manual configuration.

```python
from casa_uia import CasaAdapter

adapter = CasaAdapter(gate_url="https://casa-gate.onrender.com")

# LangChain
result = adapter.evaluate(
    framework="langchain",
    action=agent_action,    # AgentAction or tool call dict — pass as-is
    domain="pe_fund"        # optional: activates domain-specific thresholds
)

# OpenAI function calling
result = adapter.evaluate(
    framework="openai",
    action=response.choices[0].message.tool_calls[0],  # tool_calls array item
    domain="financial"
)

# CrewAI
result = adapter.evaluate(
    framework="crewai",
    action=task,            # Task dict — backstory parsed for spending limits automatically
    domain="pe_fund"
)

# All three return the same verdict interface
if result.verdict == "REFUSE":
    raise ExecutionBlocked(result.trace_id)

if result.verdict == "GOVERN":
    apply_constraints(result.constraints)
```

The UIA produces a full 9-field CAV with per-field confidence scores. Low-confidence fields default to conservative values — the gate always sees the most restricted plausible interpretation of ambiguous inputs.

**UIA is available in the enterprise package.** Contact: chrisherndonsr@gmail.com

---

## Pattern 1: Agent Runtime (Most Common)

Your orchestration framework separates action proposal from action execution. Insert CASA between the two.

```python
from casa_client import CASAClient, CanonicalActionVector, Verdict
from casa_client import ActorClass, ActionClass, TargetClass
from casa_client import Scope, Magnitude, Authorization, Timing, Consent, Reversibility

casa = CASAClient(gate_url="http://your-casa-runtime:8000", api_key="your-key")

def governed_execute(tool_call, caller_context):
    """
    Wrap any agent tool call with CASA governance.
    Call this instead of invoking the tool directly.
    """

    # Derive the CAV from request metadata — not from parsing content.
    # Your endpoint registry, auth context, and resource schema
    # should make this derivation automatic.
    vector = CanonicalActionVector(
        actor_class   = derive_actor_class(caller_context),
        action_class  = TOOL_REGISTRY[tool_call.name].action_class,
        target_class  = RESOURCE_SCHEMA[tool_call.target_type].target_class,
        scope         = compute_scope(tool_call.parameters),
        magnitude     = compute_magnitude(tool_call, DOMAIN_THRESHOLDS),
        authorization = check_authorization(caller_context, tool_call),
        timing        = derive_timing(caller_context.sla_metadata),
        consent       = check_consent(tool_call, caller_context.approval_tokens),
        reversibility = RESOURCE_SCHEMA[tool_call.target_type].reversibility,
    )

    result = casa.evaluate(vector)

    # Verdict gates what happens next.
    if result.verdict == Verdict.REFUSE:
        log_refusal(result.trace_id, result.trace_hash)
        raise ExecutionRefused(f"Gate refused execution. Trace: {result.trace_id}")

    if result.verdict == Verdict.GOVERN:
        # Apply binding structural constraints before invocation.
        tool_call = apply_constraints(tool_call, result.constraints)

    # ACCEPT or constrained GOVERN — proceed.
    return invoke_tool(tool_call)
```

---

## Pattern 2: API Gateway

Insert CASA as a reverse proxy in front of your execution endpoints. No changes to downstream services.

```python
from fastapi import FastAPI, Request, HTTPException
from casa_client import CASAClient, Verdict
import httpx

app = FastAPI()
casa = CASAClient(gate_url="http://casa-runtime:8000", api_key="your-key")
downstream = "http://your-execution-service:9000"

@app.middleware("http")
async def casa_gate_middleware(request: Request, call_next):
    # Derive CAV from request metadata.
    vector = await derive_vector_from_request(request)

    result = await casa.evaluate_async(vector)

    if result.verdict == Verdict.REFUSE:
        raise HTTPException(
            status_code=403,
            detail={
                "blocked_by": "CASA",
                "trace_id": result.trace_id,
                "trace_hash": result.trace_hash,
            }
        )

    if result.verdict == Verdict.GOVERN:
        # Attach constraints to request for downstream enforcement.
        request.state.casa_constraints = result.constraints

    # Log every trace regardless of verdict.
    await store_trace(result.raw_trace)

    return await call_next(request)
```

---

## Pattern 3: Sidecar Service

Your application calls CASA before each execution. Suitable when you need fine-grained control over when the gate is consulted.

```python
class AgentOrchestrator:
    def __init__(self):
        self.casa = CASAClient(
            gate_url="http://localhost:8000",
            api_key="your-key",
        )

    def execute_action(self, action_request):
        # 1. Build the CAV
        vector = self.build_vector(action_request)

        # 2. Evaluate
        gate_result = self.casa.evaluate(vector)

        # 3. Record the trace regardless of verdict
        self.audit_store.record(gate_result.raw_trace)

        # 4. Act on verdict
        match gate_result.verdict:
            case Verdict.ACCEPT:
                return self.invoke(action_request)

            case Verdict.GOVERN:
                constrained = self.apply_constraints(action_request, gate_result.constraints)
                result = self.invoke(constrained)
                self.validate_postconditions(result, gate_result.constraints)
                return result

            case Verdict.REFUSE:
                return ActionRefused(
                    trace_id=gate_result.trace_id,
                    reason="CASA gate refused execution"
                )
```

---

## Pattern 4: Embedded Library

For high-throughput, low-latency environments — the gate runs in-process.

```python
# No network call. Gate evaluates in-process.
from casa_runtime import CASAGate

gate = CASAGate.from_config("casa_config.yaml")

def execute(request):
    vector = derive_vector(request)
    result = gate.evaluate(vector)   # ~10ms in-process

    if result.verdict == "REFUSE":
        return blocked(result)

    return invoke_downstream(request, result.constraints)
```

*The embedded library is available under enterprise license.*

---

## CAV Derivation: The Configuration Work

The Canonical Action Vector is derived from request metadata, not from parsing content. This means you configure the mappings once at deployment:

**Endpoint/tool registry** — maps every API endpoint or tool name to `action_class` and `target_class`

```yaml
# casa_endpoint_registry.yaml
endpoints:
  DELETE /api/customers/{id}:
    action_class: DELETE
    target_class: PRINCIPAL
  POST /api/payments/transfer:
    action_class: TRANSFER
    target_class: RESOURCE
  GET /api/reports/financial:
    action_class: QUERY
    target_class: DATA
```

**Domain thresholds** — defines what counts as TRIVIAL / MATERIAL / CRITICAL in your domain

```yaml
# casa_domain_config.yaml (financial example)
magnitude_thresholds:
  trivial_ceiling:  1000      # < $1,000 = TRIVIAL
  critical_floor:   100000    # >= $100,000 = CRITICAL
```

**Resource schema** — defines `reversibility` properties for each resource type

```yaml
resource_schema:
  customer_record:
    reversibility: COSTLY       # soft delete, 30-day recovery
  financial_transfer:
    reversibility: IRREVERSIBLE # settled transfers cannot be recalled
  session_data:
    reversibility: REVERSIBLE   # backed up, recoverable
```

Once these registries are configured, CAV derivation is automatic for every request.

---

## Fail-Closed Policy

If the gate is unreachable or returns an error, **do not proceed with execution.**

```python
from casa_client import CASAClient, GateUnavailable, GateError

try:
    result = casa.evaluate(vector)
except (GateUnavailable, GateError) as e:
    # Treat gate failure the same as REFUSE.
    # Log with the request context for later audit.
    log.error(f"CASA gate failure: {e}. Blocking execution by policy.")
    raise ExecutionBlocked("Gate unavailable — fail-closed policy applied")
```

The gate itself enforces this: if a gate evaluation times out internally, it resolves to REFUSE. Your integration should enforce the same policy for network failures.

---

## Trace Storage

Store every CASA-T1 trace. The trace is the audit artifact.

```python
async def store_trace(trace: dict):
    await audit_db.insert({
        "trace_id":   trace["trace_id"],
        "trace_hash": trace["trace_hash"],
        "timestamp":  trace["timestamp"],
        "verdict":    trace["resolution"]["verdict"],
        "neg_ratio":  trace["resolution"]["neg_ratio"],
        "vector":     trace["input"]["canonical_vector"],
        "full_trace": trace,   # store complete record
    })
```

The `trace_hash` enables independent verification: any party with access to the trace can recompute the SHA-256 and confirm the record has not been modified.

---

## Enterprise Runtime

The full CASA Runtime — gate engine, constitutional graph, propagation engine, domain modules, CASA Studio, CASA Trace — is available under enterprise license.

Contact: **chrisherndonsr@gmail.com**

---

*© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC*
