"""
CASA UIA — CasaAdapter
=======================
The public-facing orchestrator. Takes a framework-native tool call,
runs it through the CNL, and submits the resulting CAV to the CASA gate.

This is the integration surface. One class. One method: evaluate().

Usage:

    from casa_uia import CasaAdapter

    adapter = CasaAdapter(gate_url="https://casa-gate.onrender.com")

    # With an OpenAI tool call
    result = adapter.evaluate(
        framework="openai",
        tool_call=tool_call_object,
        authorization_context={"role": "capital_allocator", "spending_limit": 500000},
        caller_id="agent-pe-001",
        domain="pe_fund",
    )

    if result.gate_result.execution_blocked:
        raise RuntimeError(f"Execution refused. Trace: {result.gate_result.trace_id}")

© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC
USPTO Provisional Patent #63/987,813
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from .cnl.pipeline import ConstitutionalNormalizationLayer
from .models import (
    CanonicalActionVector,
    NormalizationMetadata,
    NormalizationResult,
    NormalizationStatus,
)
from .shims.langchain_shim import LangChainShim
from .shims.openai_shim import OpenAIToolCallShim

logger = logging.getLogger(__name__)

# Default live gate
DEFAULT_GATE_URL = "https://casa-gate.onrender.com"


# ─────────────────────────────────────────────────────────────
# Gate result types (mirror of sdk/python/casa_client.py)
# ─────────────────────────────────────────────────────────────

@dataclass
class GateConstraint:
    type: str
    target: str
    requirement: str
    source_primitive: str


@dataclass
class GateResult:
    verdict: str                    # ACCEPT | GOVERN | REFUSE
    trace_id: str
    trace_hash: str
    timestamp: str
    pos_mass: float
    neg_mass: float
    neg_ratio: float
    hard_stop_fired: bool
    constraints: List[GateConstraint] = field(default_factory=list)
    raw_response: Optional[Dict[str, Any]] = None

    @property
    def execution_permitted(self) -> bool:
        return self.verdict in ("ACCEPT", "GOVERN")

    @property
    def execution_blocked(self) -> bool:
        return self.verdict == "REFUSE"


# ─────────────────────────────────────────────────────────────
# Adapter result
# ─────────────────────────────────────────────────────────────

@dataclass
class AdapterResult:
    """Complete result from the UIA pipeline."""

    # Normalization
    normalization_result: NormalizationResult

    # Gate result (None if normalization failed or gate unreachable)
    gate_result: Optional[GateResult] = None

    # Error (set if gate call failed)
    gate_error: Optional[str] = None

    @property
    def cav(self) -> Optional[CanonicalActionVector]:
        return self.normalization_result.cav

    @property
    def metadata(self) -> Optional[NormalizationMetadata]:
        return self.normalization_result.metadata

    @property
    def normalization_status(self) -> Optional[NormalizationStatus]:
        return self.metadata.normalization_status if self.metadata else None

    @property
    def execution_blocked(self) -> bool:
        """
        True if execution must not proceed.
        Blocked by gate REFUSE OR normalization failure (fail-closed).
        """
        if not self.normalization_result.success:
            return True
        if self.gate_result and self.gate_result.execution_blocked:
            return True
        if self.gate_error:
            # Fail-closed: gate unreachable = blocked
            return True
        return False

    @property
    def verdict(self) -> str:
        """Human-readable verdict summary."""
        if not self.normalization_result.success:
            return f"BLOCKED (normalization failed: {self.normalization_result.blocked_reason})"
        if self.gate_error:
            return f"BLOCKED (gate error: {self.gate_error})"
        if self.gate_result:
            return self.gate_result.verdict
        return "UNKNOWN"

    def summary(self) -> str:
        """One-paragraph result summary for logging and debugging."""
        lines = [
            f"Verdict: {self.verdict}",
            f"Normalization status: {self.normalization_status.value if self.normalization_status else 'N/A'}",
        ]
        if self.cav:
            lines.append(
                f"CAV: {self.cav.actor_class.value} / {self.cav.action_class.value} / "
                f"{self.cav.target_class.value} / {self.cav.scope.value} / "
                f"{self.cav.magnitude.value} / {self.cav.authorization.value} / "
                f"{self.cav.timing.value} / {self.cav.consent.value} / "
                f"{self.cav.reversibility.value}"
            )
        if self.metadata:
            lines.append(
                f"Confidence: mean={self.metadata.mean_confidence:.3f} "
                f"min={self.metadata.minimum_confidence:.3f} "
                f"defaults={self.metadata.default_field_count}"
            )
        if self.gate_result:
            lines.append(
                f"Gate: trace_id={self.gate_result.trace_id} "
                f"neg_ratio={self.gate_result.neg_ratio:.4f} "
                f"hard_stop={self.gate_result.hard_stop_fired}"
            )
        return " | ".join(lines)


# ─────────────────────────────────────────────────────────────
# CasaAdapter
# ─────────────────────────────────────────────────────────────

class CasaAdapter:
    """
    The CASA Universal Intake Adapter.

    Accepts any supported framework's tool call format,
    normalizes it through the CNL, and evaluates it against the CASA gate.

    Supported frameworks:
      - "openai"    — OpenAI Chat Completions tool_calls format
      - "langchain" — LangChain AgentAction / tool call dict
      - "iio"       — Pass a pre-built IIO directly (advanced)
    """

    SUPPORTED_FRAMEWORKS = {"openai", "langchain", "iio"}

    def __init__(
        self,
        gate_url: str = DEFAULT_GATE_URL,
        api_key: Optional[str] = None,
        timeout: int = 10,
        fail_closed: bool = True,
    ):
        """
        Args:
            gate_url: CASA gate base URL
            api_key: Optional API key for authenticated gate instances
            timeout: HTTP timeout in seconds
            fail_closed: If True (default), treat gate errors as REFUSE
        """
        self.gate_url = gate_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.fail_closed = fail_closed

        self._cnl = ConstitutionalNormalizationLayer()
        self._openai_shim = OpenAIToolCallShim()
        self._langchain_shim = LangChainShim()

        logger.info(f"CasaAdapter initialized — gate: {self.gate_url}")

    def evaluate(
        self,
        framework: str,
        tool_call: Any,
        authorization_context: Optional[Dict[str, Any]] = None,
        caller_id: Optional[str] = None,
        caller_role: Optional[str] = None,
        domain: Optional[str] = None,
        tool_call_index: int = 0,
    ) -> AdapterResult:
        """
        Evaluate a tool call through the full UIA pipeline.

        Args:
            framework: "openai", "langchain", or "iio"
            tool_call: Framework-native tool call object
            authorization_context: Auth context dict from calling system
            caller_id: Identity of the caller
            caller_role: Role of the caller
            domain: Domain hint for threshold selection
            tool_call_index: For OpenAI tool_calls lists, which index to use

        Returns:
            AdapterResult with normalization result, CAV, and gate verdict
        """
        if framework not in self.SUPPORTED_FRAMEWORKS:
            norm_result = NormalizationResult(
                success=False,
                blocked_reason=f"Unsupported framework: '{framework}'. Supported: {self.SUPPORTED_FRAMEWORKS}",
            )
            return AdapterResult(normalization_result=norm_result)

        # ── Shim: extract IIO ─────────────────────────────────────────
        from .models import IntermediateIntentObject

        if framework == "openai":
            iio = self._openai_shim.extract(
                tool_call=tool_call,
                authorization_context=authorization_context,
                caller_id=caller_id,
                caller_role=caller_role,
                domain=domain,
                tool_call_index=tool_call_index,
            )
        elif framework == "langchain":
            iio = self._langchain_shim.extract(
                agent_action=tool_call,
                authorization_context=authorization_context,
                caller_id=caller_id,
                caller_role=caller_role,
                domain=domain,
            )
        elif framework == "iio":
            if not isinstance(tool_call, IntermediateIntentObject):
                norm_result = NormalizationResult(
                    success=False,
                    blocked_reason="framework='iio' requires tool_call to be an IntermediateIntentObject",
                )
                return AdapterResult(normalization_result=norm_result)
            iio = tool_call

        # ── CNL: normalize IIO → CAV ──────────────────────────────────
        norm_result = self._cnl.normalize(iio)

        if not norm_result.success:
            logger.warning(
                f"CNL normalization failed: {norm_result.blocked_reason}"
            )
            return AdapterResult(normalization_result=norm_result)

        # If AMBIGUOUS, CAV will be submitted but gate behavior is conservative
        # (AMBIGUOUS status is noted in the gate payload as metadata)

        # ── Gate: evaluate CAV ────────────────────────────────────────
        gate_result, gate_error = self._call_gate(norm_result.cav)

        return AdapterResult(
            normalization_result=norm_result,
            gate_result=gate_result,
            gate_error=gate_error,
        )

    def _call_gate(
        self, cav: CanonicalActionVector
    ) -> tuple[Optional[GateResult], Optional[str]]:
        """Submit CAV to gate. Returns (GateResult, error_string)."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Build gate payload — nine CAV fields only (gate schema is strict)
        payload = cav.to_gate_dict()

        try:
            response = requests.post(
                f"{self.gate_url}/evaluate",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_gate_response(data), None

        except requests.exceptions.ConnectionError:
            msg = "CASA gate unreachable — fail-closed policy applied"
            logger.error(msg)
            return None, msg

        except requests.exceptions.Timeout:
            msg = f"CASA gate timeout ({self.timeout}s) — fail-closed policy applied"
            logger.error(msg)
            return None, msg

        except requests.exceptions.HTTPError as exc:
            msg = f"CASA gate HTTP error: {exc}"
            logger.error(msg)
            return None, msg

        except Exception as exc:
            msg = f"Unexpected gate call error: {exc}"
            logger.exception(msg)
            return None, msg

    @staticmethod
    def _parse_gate_response(data: Dict[str, Any]) -> GateResult:
        constraints = [
            GateConstraint(
                type=c.get("type", ""),
                target=c.get("target", ""),
                requirement=c.get("requirement", ""),
                source_primitive=c.get("source_primitive", ""),
            )
            for c in data.get("constraints", [])
        ]
        return GateResult(
            verdict=data.get("verdict", "REFUSE"),
            trace_id=data.get("trace_id", ""),
            trace_hash=data.get("trace_hash", ""),
            timestamp=data.get("timestamp", ""),
            pos_mass=data.get("propagation", {}).get("pos_mass", 0.0),
            neg_mass=data.get("propagation", {}).get("neg_mass", 0.0),
            neg_ratio=data.get("neg_ratio", 0.0),
            hard_stop_fired=data.get("hard_stop", False),
            constraints=constraints,
            raw_response=data,
        )

    def health(self) -> Dict[str, Any]:
        """Check gate health."""
        response = requests.get(f"{self.gate_url}/health", timeout=self.timeout)
        response.raise_for_status()
        return response.json()
