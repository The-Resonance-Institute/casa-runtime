"""
CASA Runtime Client — Python SDK
=================================
Minimal integration example showing the CASA gate call contract.

The gate accepts a Canonical Action Vector and returns a verdict with
a complete CASA-T1 audit trace.

Live gate for immediate evaluation (no setup required):
  https://casa-gate.onrender.com/docs

This is the public interface. The gate implementation is available
under NDA and enterprise license.

Contact: contact@resonanceinstitutellc.com
© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC
"""

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
import requests


# ─────────────────────────────────────────────
# Canonical Action Vector — the gate's input
# ─────────────────────────────────────────────

class ActorClass(str, Enum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"
    SERVICE = "SERVICE"
    SCHEDULED = "SCHEDULED"
    EXTERNAL = "EXTERNAL"

class ActionClass(str, Enum):
    QUERY = "QUERY"
    CREATE = "CREATE"
    MODIFY = "MODIFY"
    DELETE = "DELETE"
    TRANSFER = "TRANSFER"
    EXECUTE = "EXECUTE"
    ESCALATE = "ESCALATE"

class TargetClass(str, Enum):
    SELF = "SELF"
    DATA = "DATA"
    RESOURCE = "RESOURCE"
    PRINCIPAL = "PRINCIPAL"
    GROUP = "GROUP"
    SYSTEM = "SYSTEM"

class Scope(str, Enum):
    SINGLE = "SINGLE"
    BOUNDED = "BOUNDED"
    UNBOUNDED = "UNBOUNDED"

class Magnitude(str, Enum):
    TRIVIAL = "TRIVIAL"
    MATERIAL = "MATERIAL"
    CRITICAL = "CRITICAL"

class Authorization(str, Enum):
    WITHIN_GRANT = "WITHIN_GRANT"
    AT_LIMIT = "AT_LIMIT"
    EXCEEDS_GRANT = "EXCEEDS_GRANT"

class Timing(str, Enum):
    ROUTINE = "ROUTINE"
    EXPEDITED = "EXPEDITED"
    IMMEDIATE = "IMMEDIATE"

class Consent(str, Enum):
    EXPLICIT = "EXPLICIT"
    IMPLIED = "IMPLIED"
    NONE = "NONE"

class Reversibility(str, Enum):
    REVERSIBLE = "REVERSIBLE"
    COSTLY = "COSTLY"
    IRREVERSIBLE = "IRREVERSIBLE"


@dataclass
class CanonicalActionVector:
    """
    The nine-field metadata representation of any structured execution request.

    Fields are derived deterministically from request metadata:
    endpoint registry lookups, authentication context, resource schemas,
    domain thresholds, role grants, SLA metadata, approval tokens.

    No field requires content interpretation.
    The natural language payload of a request is opaque to CASA.
    """
    actor_class: ActorClass
    action_class: ActionClass
    target_class: TargetClass
    scope: Scope
    magnitude: Magnitude
    authorization: Authorization
    timing: Timing
    consent: Consent
    reversibility: Reversibility

    def to_dict(self) -> Dict[str, str]:
        return {
            "actor_class": self.actor_class.value,
            "action_class": self.action_class.value,
            "target_class": self.target_class.value,
            "scope": self.scope.value,
            "magnitude": self.magnitude.value,
            "authorization": self.authorization.value,
            "timing": self.timing.value,
            "consent": self.consent.value,
            "reversibility": self.reversibility.value,
        }


# ─────────────────────────────────────────────
# Gate verdict
# ─────────────────────────────────────────────

class Verdict(str, Enum):
    ACCEPT = "ACCEPT"   # Execution proceeds without constraints
    GOVERN = "GOVERN"   # Execution proceeds with binding structural constraints
    REFUSE = "REFUSE"   # Execution blocked. No downstream system is invoked.


@dataclass
class CASAConstraint:
    """A binding structural constraint emitted for GOVERN verdicts."""
    type: str           # FIELD_REQUIRED | ENUM_RESTRICTION | SCHEMA_COMPLIANCE | TOKEN_BUDGET | DISCLOSURE
    target: str         # Field name or schema path
    requirement: str    # Description of the requirement
    source_primitive: str  # CP### — the primitive that triggered this constraint


@dataclass
class GateResult:
    """
    Complete gate result with CASA-T1 compliant audit trace.

    The trace_hash is a SHA-256 of the complete trace content.
    Any modification to any field changes the hash.
    An auditor can independently verify any decision.
    """
    verdict: Verdict
    trace_id: str
    trace_hash: str
    timestamp: str

    # Resolution detail
    pos_mass: float
    neg_mass: float
    neg_ratio: float
    hard_stop_fired: bool

    # Constraints (populated for GOVERN verdicts)
    constraints: List[CASAConstraint] = field(default_factory=list)

    # Full trace (available for audit)
    raw_trace: Optional[Dict[str, Any]] = None

    @property
    def execution_permitted(self) -> bool:
        """True if downstream execution is permitted (ACCEPT or GOVERN)."""
        return self.verdict in (Verdict.ACCEPT, Verdict.GOVERN)

    @property
    def execution_blocked(self) -> bool:
        """True if downstream execution is unconditionally blocked (REFUSE)."""
        return self.verdict == Verdict.REFUSE


# ─────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────

class CASAClient:
    """
    Client for the CASA Runtime gate API.

    For immediate evaluation against the live public gate:
        client = CASAClient(gate_url="https://casa-gate.onrender.com")

    For enterprise deployment with API key:
        client = CASAClient(gate_url="https://your-gate-host", api_key="your-key")

    Usage:
        client = CASAClient(gate_url="https://casa-gate.onrender.com")

        vector = CanonicalActionVector(
            actor_class=ActorClass.AGENT,
            action_class=ActionClass.DELETE,
            target_class=TargetClass.PRINCIPAL,
            scope=Scope.SINGLE,
            magnitude=Magnitude.MATERIAL,
            authorization=Authorization.WITHIN_GRANT,
            timing=Timing.ROUTINE,
            consent=Consent.EXPLICIT,
            reversibility=Reversibility.COSTLY,
        )

        result = client.evaluate(vector)

        if result.execution_blocked:
            raise ExecutionRefused(result.trace_id)

        if result.verdict == Verdict.GOVERN:
            apply_constraints(result.constraints)

        proceed_with_execution()
    """

    # Live public gate — no API key required for evaluation
    PUBLIC_GATE_URL = "https://casa-gate.onrender.com"

    def __init__(self, gate_url: str = PUBLIC_GATE_URL, api_key: str = None, timeout: int = 10):
        self.gate_url = gate_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def evaluate(self, vector: CanonicalActionVector) -> GateResult:
        """
        Submit a Canonical Action Vector to the gate and receive a verdict.

        Raises:
            GateUnavailable: If the gate cannot be reached (fail-closed — treat as REFUSE)
            GateError: If the gate returns an error (fail-closed — treat as REFUSE)
        """
        # Map nine-field CAV to live gate schema
        payload = {
            "action_class": vector.action_class.value,
            "target_type": vector.target_class.value,
            "content": "",
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = requests.post(
                f"{self.gate_url}/evaluate",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise GateUnavailable("CASA gate unreachable — applying fail-closed policy")
        except requests.exceptions.Timeout:
            raise GateUnavailable("CASA gate timeout — applying fail-closed policy")
        except requests.exceptions.HTTPError as e:
            raise GateError(f"CASA gate error: {e}")

        data = response.json()
        return self._parse_result(data)

    def _parse_result(self, data: Dict[str, Any]) -> GateResult:
        constraints = [
            CASAConstraint(
                type=c.get("type", ""),
                target=c.get("target", ""),
                requirement=c.get("requirement", ""),
                source_primitive=c.get("source_primitive", ""),
            )
            for c in data.get("constraints", [])
        ]

        return GateResult(
            verdict=Verdict(data["verdict"]),
            trace_id=data["trace_id"],
            trace_hash=data["trace_hash"],
            timestamp=data["timestamp"],
            pos_mass=data.get("propagation", {}).get("pos_mass", 0.0),
            neg_mass=data.get("propagation", {}).get("neg_mass", 0.0),
            neg_ratio=data.get("neg_ratio", 0.0),
            hard_stop_fired=data.get("hard_stop", False),
            constraints=constraints,
            raw_trace=data,
        )

    def health(self) -> Dict[str, Any]:
        """Check gate health and version."""
        response = requests.get(
            f"{self.gate_url}/health",
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


class GateUnavailable(Exception):
    """Gate could not be reached. Apply fail-closed policy: treat as REFUSE."""
    pass

class GateError(Exception):
    """Gate returned an error. Apply fail-closed policy: treat as REFUSE."""
    pass

class ExecutionRefused(Exception):
    """Gate returned REFUSE. Downstream execution must not proceed."""
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        super().__init__(f"Execution refused by CASA gate. Trace: {trace_id}")


# ─────────────────────────────────────────────
# Example: agent action governance
# ─────────────────────────────────────────────

def example_agent_action_governance():
    """
    Example: governing an AI agent's proposed tool call before execution.

    The agent has proposed deleting a customer record.
    Before any downstream system is touched, we ask CASA.

    Run this example against the live public gate:
        python casa_client.py
    """

    # Connect to live public gate — no API key required
    client = CASAClient(gate_url=CASAClient.PUBLIC_GATE_URL)

    # Agent proposed: delete_customer_record(customer_id=12345)
    # We derive the CAV from the request metadata — not from parsing the content.
    vector = CanonicalActionVector(
        actor_class=ActorClass.AGENT,        # from service account auth context
        action_class=ActionClass.DELETE,     # from tool registry mapping
        target_class=TargetClass.PRINCIPAL,  # from resource schema (customer = principal data)
        scope=Scope.SINGLE,                  # single record targeted
        magnitude=Magnitude.MATERIAL,        # customer record deletion > trivial threshold
        authorization=Authorization.WITHIN_GRANT,  # agent role includes customer management
        timing=Timing.ROUTINE,               # standard queue priority
        consent=Consent.EXPLICIT,            # deletion request includes approval token
        reversibility=Reversibility.COSTLY,  # soft delete, 30-day recovery window
    )

    result = client.evaluate(vector)

    print(f"Verdict:    {result.verdict.value}")
    print(f"Trace ID:   {result.trace_id}")
    print(f"Trace hash: {result.trace_hash}")
    print(f"neg_ratio:  {result.neg_ratio:.4f}")

    if result.execution_blocked:
        # Unconditional. Do not invoke any downstream system.
        raise ExecutionRefused(result.trace_id)

    if result.verdict == Verdict.GOVERN:
        print(f"Constraints ({len(result.constraints)}):")
        for c in result.constraints:
            print(f"  [{c.source_primitive}] {c.type}: {c.requirement}")

    print("Execution permitted. Proceeding.")


if __name__ == "__main__":
    example_agent_action_governance()
