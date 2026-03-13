"""
CASA UIA — Core Data Models
============================
Intermediate Intent Object (IIO), Canonical Action Vector (CAV),
normalization metadata, and all supporting enums.

Architectural Law #2: The normalizer must never hallucinate completeness.
Every field carries an explicit confidence score and normalization status.

© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC
USPTO Provisional Patent #63/987,813
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────
# CAV Enums (matches live gate schema exactly)
# ─────────────────────────────────────────────────────────────

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
    COMMUNICATE = "COMMUNICATE"  # Extended from gate spec; maps to EXECUTE at gate boundary


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


# ─────────────────────────────────────────────────────────────
# Normalization Status
# ─────────────────────────────────────────────────────────────

class NormalizationStatus(str, Enum):
    COMPLETE = "COMPLETE"       # All nine fields resolved with high confidence
    PARTIAL = "PARTIAL"         # Some fields resolved; defaults applied to remainder
    AMBIGUOUS = "AMBIGUOUS"     # Low confidence on one or more fields; gate escalates to GOVERN
    FAILED = "FAILED"           # Cannot produce a defensible CAV; submission blocked


# ─────────────────────────────────────────────────────────────
# Intermediate Intent Object (IIO)
# ─────────────────────────────────────────────────────────────
#
# Produced by shims. Contains raw extracted fields only.
# No governance logic. No CAV field inference. No defaults.
# Architectural Law #1: Shims extract. They do not govern.
# ─────────────────────────────────────────────────────────────

@dataclass
class IntermediateIntentObject:
    """
    The IIO is the shim's output and the CNL's input.

    All fields are prefixed raw_ to enforce the extraction-only contract.
    The CNL reads these fields and produces CAV values.
    A shim may leave any field None if it cannot extract it.
    """

    # Source metadata
    source_framework: str                           # "openai_tool_call" | "langchain" | "custom_json"
    raw_request_id: Optional[str] = None            # Passthrough request correlation ID

    # Layer 1 extractions — direct structural fields
    raw_tool_name: Optional[str] = None             # Tool or endpoint name as called
    raw_tool_args: Optional[Dict[str, Any]] = None  # Tool arguments, unparsed
    raw_caller_id: Optional[str] = None             # Agent/user/service identity string
    raw_caller_role: Optional[str] = None           # Role string from auth context
    raw_authorization_context: Optional[Dict[str, Any]] = None  # Full auth object

    # Layer 1 extractions — target
    raw_target_resource: Optional[str] = None       # Resource type string
    raw_target_id: Optional[str] = None             # Specific resource ID if present

    # Layer 1 extractions — numeric signals
    raw_amount: Optional[float] = None              # Numeric amount if present (financial)
    raw_record_count: Optional[int] = None          # Record count if present
    raw_currency: Optional[str] = None              # Currency code if present

    # Layer 1 extractions — context signals
    raw_approval_tokens: Optional[List[str]] = None # Approval/consent token list
    raw_priority_flag: Optional[str] = None         # Priority or urgency signal
    raw_domain: Optional[str] = None                # Domain context hint
    raw_scope_qualifier: Optional[str] = None       # Scope hint ("all", "bounded", specific ID)

    # Extraction trace — populated by shim
    extraction_warnings: List[str] = field(default_factory=list)
    extraction_timestamp: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Field Confidence
# ─────────────────────────────────────────────────────────────

@dataclass
class FieldConfidence:
    """Per-field confidence score and derivation source."""
    field_name: str
    value: Any                      # The resolved CAV value
    confidence: float               # 0.0 - 1.0
    derivation: str                 # Human-readable trace of how value was derived
    is_default: bool = False        # True if conservative default was applied
    assumption: Optional[str] = None  # If is_default, describe the assumption


# ─────────────────────────────────────────────────────────────
# Normalization Metadata
# ─────────────────────────────────────────────────────────────

@dataclass
class NormalizationMetadata:
    """
    Complete normalization audit record.
    Attached to every CAV before gate submission.
    """
    normalization_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_framework: str = ""
    normalization_status: NormalizationStatus = NormalizationStatus.FAILED
    field_confidences: List[FieldConfidence] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    normalization_trace: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def minimum_confidence(self) -> float:
        if not self.field_confidences:
            return 0.0
        return min(fc.confidence for fc in self.field_confidences)

    @property
    def mean_confidence(self) -> float:
        if not self.field_confidences:
            return 0.0
        return sum(fc.confidence for fc in self.field_confidences) / len(self.field_confidences)

    @property
    def default_field_count(self) -> int:
        return sum(1 for fc in self.field_confidences if fc.is_default)

    def add_trace(self, message: str) -> None:
        self.normalization_trace.append(message)

    def add_assumption(self, assumption: str) -> None:
        self.assumptions.append(assumption)
        self.normalization_trace.append(f"ASSUMPTION: {assumption}")

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)
        self.normalization_trace.append(f"WARNING: {warning}")

    def add_error(self, error: str) -> None:
        self.errors.append(error)
        self.normalization_trace.append(f"ERROR: {error}")


# ─────────────────────────────────────────────────────────────
# Canonical Action Vector (with metadata)
# ─────────────────────────────────────────────────────────────

@dataclass
class CanonicalActionVector:
    """
    The nine-field governance input to the CASA gate.
    When produced by the CNL, always carries normalization_metadata.
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

    # Populated when produced via CNL normalization
    normalization_metadata: Optional[NormalizationMetadata] = None

    # Maps UIA action_class to gate semantic action_class
    _ACTION_TO_GATE = {
        "QUERY":     "QUERY",
        "CREATE":    "CREATE",
        "MODIFY":    "MANIPULATE",
        "DELETE":    "MANIPULATE",
        "TRANSFER":  "MANIPULATE",
        "EXECUTE":   "MANIPULATE",
        "ESCALATE":  "MANIPULATE",
        "COMMUNICATE": "ADVISE",
    }

    # Maps UIA target_class to gate semantic target_type
    _TARGET_TO_GATE = {
        "SELF":      "SELF",
        "DATA":      "INFORMATION",
        "RESOURCE":  "INSTITUTION",
        "PRINCIPAL": "PERSON_CONSENTING",
        "GROUP":     "GROUP",
        "SYSTEM":    "INSTITUTION",
    }

    def to_gate_dict(self) -> Dict[str, str]:
        """
        Serialize to the live gate API format.
        The live gate uses a semantic schema: action_class, target_type, content.
        UIA CAV fields are translated via registry maps.
        """
        gate_action = self._ACTION_TO_GATE.get(self.action_class.value, "MANIPULATE")
        gate_target = self._TARGET_TO_GATE.get(self.target_class.value, "INSTITUTION")

        # Build a content summary from the high-risk CAV fields for gate context
        risk_signals = []
        if self.authorization.value == "EXCEEDS_GRANT":
            risk_signals.append("exceeds authorization")
        if self.consent.value == "NONE":
            risk_signals.append("no consent")
        if self.magnitude.value == "CRITICAL":
            risk_signals.append("critical magnitude")
        if self.reversibility.value == "IRREVERSIBLE":
            risk_signals.append("irreversible")
        content = "; ".join(risk_signals) if risk_signals else ""

        return {
            "action_class": gate_action,
            "target_type": gate_target,
            "content": content,
        }

    def to_dict(self) -> Dict[str, str]:
        """Full serialization including internal action classes."""
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


# ─────────────────────────────────────────────────────────────
# Normalization Result — what the CNL returns
# ─────────────────────────────────────────────────────────────

@dataclass
class NormalizationResult:
    """
    Complete output of a CNL normalization pass.
    Either contains a CAV ready for gate submission, or a FAILED status with errors.
    """
    success: bool
    cav: Optional[CanonicalActionVector] = None
    metadata: Optional[NormalizationMetadata] = None
    blocked_reason: Optional[str] = None  # If success=False, why normalization was blocked

    @property
    def requires_escalation(self) -> bool:
        """True if low confidence requires automatic GOVERN escalation."""
        if not self.metadata:
            return False
        return self.metadata.normalization_status == NormalizationStatus.AMBIGUOUS

    @property
    def ready_for_gate(self) -> bool:
        """True if CAV can be submitted to the gate."""
        return self.success and self.cav is not None
