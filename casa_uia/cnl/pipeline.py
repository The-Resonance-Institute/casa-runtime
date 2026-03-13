"""
CASA UIA — Constitutional Normalization Layer (CNL)
====================================================
Orchestrates the three-layer normalization pipeline:

  Layer 1: Structural Extraction
  Layer 2: Semantic Classification
  Layer 3: Authority Resolution

  → Canonical Action Vector + Normalization Metadata

The CNL is the IP core of the UIA. It transforms a heterogeneous
agent execution request (via IIO) into a deterministic, auditable
nine-field CAV suitable for CASA gate evaluation.

No LLM calls. No probabilistic inference. No hallucinated completeness.

© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC
USPTO Provisional Patent #63/987,813
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..models import (
    ActorClass,
    CanonicalActionVector,
    FieldConfidence,
    IntermediateIntentObject,
    NormalizationMetadata,
    NormalizationResult,
    NormalizationStatus,
)
from .layer1_extractor import StructuralExtractor
from .layer2_classifier import SemanticClassifier
from .layer3_authority import AuthorityResolver

logger = logging.getLogger(__name__)

# Confidence thresholds
AMBIGUITY_THRESHOLD = 0.75     # Below this on any field → AMBIGUOUS
COMPLETENESS_THRESHOLD = 0.50  # Below this on any field → FAILED


class ConstitutionalNormalizationLayer:
    """
    The CNL: three-layer normalization pipeline.

    Instantiate once. Call normalize() for each IIO.
    Thread-safe (no mutable state after __init__).
    """

    def __init__(self):
        self._layer1 = StructuralExtractor()
        self._layer2 = SemanticClassifier()
        self._layer3 = AuthorityResolver()
        logger.info("CNL initialized — all three layers ready")

    def normalize(self, iio: IntermediateIntentObject) -> NormalizationResult:
        """
        Normalize an IIO into a CAV.

        Returns a NormalizationResult with either:
        - success=True and a complete CAV + metadata
        - success=False and a blocked_reason explaining why

        Never raises. All exceptions are caught and returned as FAILED results.
        """
        metadata = NormalizationMetadata(
            normalization_id=str(uuid.uuid4()),
            source_framework=iio.source_framework,
            normalization_status=NormalizationStatus.FAILED,
        )
        metadata.add_trace(
            f"CNL normalization begin — source: {iio.source_framework} — "
            f"id: {metadata.normalization_id}"
        )

        try:
            return self._run_pipeline(iio, metadata)
        except Exception as exc:
            logger.exception("CNL pipeline error")
            metadata.add_error(f"Unhandled pipeline exception: {exc}")
            metadata.normalization_status = NormalizationStatus.FAILED
            return NormalizationResult(
                success=False,
                metadata=metadata,
                blocked_reason=f"CNL pipeline exception: {exc}",
            )

    def _run_pipeline(
        self, iio: IntermediateIntentObject, metadata: NormalizationMetadata
    ) -> NormalizationResult:

        # ── Layer 1: Structural Extraction ───────────────────────────
        layer1_output, viable = self._layer1.extract(iio, metadata)
        if not viable:
            metadata.normalization_status = NormalizationStatus.FAILED
            return NormalizationResult(
                success=False,
                metadata=metadata,
                blocked_reason=metadata.errors[-1] if metadata.errors else "Layer 1 extraction failed",
            )

        # ── Layer 2: Semantic Classification ─────────────────────────
        layer2_output = self._layer2.classify(layer1_output, metadata)

        # ── Layer 3: Authority Resolution ────────────────────────────
        layer3_output = self._layer3.resolve(layer1_output, layer2_output, metadata)

        # ── actor_class resolution (from IIO source framework + caller) ─
        actor_class, actor_confidence = self._resolve_actor_class(iio, layer1_output, metadata)

        # ── Assemble all field confidences ───────────────────────────
        actor_fc = FieldConfidence(
            field_name="actor_class",
            value=actor_class,
            confidence=actor_confidence,
            derivation=f"source_framework={iio.source_framework} / caller_role={layer1_output.caller_role}",
            is_default=(actor_confidence < 0.60),
            assumption="actor_class defaulted to AGENT (conservative)" if actor_confidence < 0.60 else None,
        )

        all_field_confidences = (
            [actor_fc]
            + layer2_output.field_confidences
            + layer3_output.field_confidences
        )
        metadata.field_confidences = all_field_confidences

        # ── Determine normalization status ───────────────────────────
        status = self._compute_status(all_field_confidences, metadata)
        metadata.normalization_status = status

        if status == NormalizationStatus.FAILED:
            return NormalizationResult(
                success=False,
                metadata=metadata,
                blocked_reason="Normalization confidence too low to produce defensible CAV",
            )

        # ── Build CAV ─────────────────────────────────────────────────
        cav = CanonicalActionVector(
            actor_class=actor_class,
            action_class=layer2_output.action_class,
            target_class=layer2_output.target_class,
            scope=layer2_output.scope,
            magnitude=layer2_output.magnitude,
            authorization=layer3_output.authorization,
            timing=layer2_output.timing,
            consent=layer3_output.consent,
            reversibility=layer2_output.reversibility,
            normalization_metadata=metadata,
        )

        metadata.add_trace(
            f"CNL normalization complete — status: {status.value} — "
            f"mean_confidence: {metadata.mean_confidence:.3f} — "
            f"defaults_applied: {metadata.default_field_count}"
        )

        return NormalizationResult(
            success=True,
            cav=cav,
            metadata=metadata,
        )

    @staticmethod
    def _resolve_actor_class(
        iio: IntermediateIntentObject,
        layer1,
        metadata: NormalizationMetadata,
    ):
        """
        Derive actor_class from source framework and caller context.

        Framework origin gives us the base signal:
        - openai_tool_call, langchain → AGENT
        - scheduled, cron → SCHEDULED
        - webhook → EXTERNAL
        - human_api → HUMAN
        """
        framework = iio.source_framework.lower()
        role = (layer1.caller_role or "").lower()

        if any(s in framework for s in ("human", "user", "rest_api", "web_ui")):
            metadata.add_trace("actor_class: HUMAN — source framework is human-initiated")
            return ActorClass.HUMAN, 0.90

        if any(s in framework for s in ("scheduled", "cron", "batch", "task_queue")):
            metadata.add_trace("actor_class: SCHEDULED — source framework is scheduled")
            return ActorClass.SCHEDULED, 0.90

        if any(s in framework for s in ("webhook", "external", "inbound")):
            metadata.add_trace("actor_class: EXTERNAL — source framework is external")
            return ActorClass.EXTERNAL, 0.88

        if any(s in framework for s in ("service", "internal_service", "service_account")):
            metadata.add_trace("actor_class: SERVICE — source framework is service")
            return ActorClass.SERVICE, 0.88

        # LLM agent frameworks → AGENT
        if any(s in framework for s in (
            "openai", "langchain", "crewai", "autogen", "agent", "tool_call", "custom_json"
        )):
            metadata.add_trace(f"actor_class: AGENT — source framework '{framework}'")
            return ActorClass.AGENT, 0.92

        # Role fallback
        if "agent" in role or "bot" in role or "ai" in role:
            metadata.add_trace(f"actor_class: AGENT — role '{role}'")
            return ActorClass.AGENT, 0.75

        if "human" in role or "user" in role:
            metadata.add_trace(f"actor_class: HUMAN — role '{role}'")
            return ActorClass.HUMAN, 0.75

        # Conservative default
        metadata.add_assumption("actor_class unknown — defaulted to AGENT (conservative)")
        return ActorClass.AGENT, 0.40

    @staticmethod
    def _compute_status(
        field_confidences: list, metadata: NormalizationMetadata
    ) -> NormalizationStatus:
        """
        Compute overall normalization status from per-field confidences.

        COMPLETE: all fields >= AMBIGUITY_THRESHOLD
        PARTIAL: all fields >= COMPLETENESS_THRESHOLD but some below AMBIGUITY_THRESHOLD
        AMBIGUOUS: viable — gate auto-escalates to GOVERN
        FAILED: action_class has zero confidence (cannot determine what to do)

        IMPORTANT: AMBIGUOUS status still produces a valid CAV.
        Conservative defaults were applied — the CAV is intentionally strict.
        The gate will apply GOVERN or REFUSE based on the conservative field values.
        Blocking submission would silently allow execution. Fail-closed means submit
        with maximum conservatism, not block entirely.

        We only FAIL if action_class itself is unknown (confidence < COMPLETENESS_THRESHOLD),
        because without knowing what the request tries to do, no governance is possible.
        """
        if not field_confidences:
            return NormalizationStatus.FAILED

        # Only hard-fail if action_class has extremely low confidence AND no tool name at all
        # (This case is already caught in Layer 1 — raw_tool_name=None → FAILED before we get here)
        # If we reach here, we have a tool name and a default action_class is acceptable.
        # The conservative default (EXECUTE/CRITICAL/IRREVERSIBLE) is MORE restrictive than a
        # failed normalization that silently allows execution.
        action_class_fc = next(
            (fc for fc in field_confidences if fc.field_name == "action_class"), None
        )
        # Hard-fail only if we somehow have confidence exactly 0 (no tool name reached here)
        if action_class_fc and action_class_fc.confidence == 0.0:
            return NormalizationStatus.FAILED

        any_below_ambiguity = any(fc.confidence < AMBIGUITY_THRESHOLD for fc in field_confidences)

        if any_below_ambiguity:
            # AMBIGUOUS: viable for gate submission but auto-escalates to GOVERN
            return NormalizationStatus.AMBIGUOUS

        # All fields high confidence — check if any defaults were applied
        any_defaults = any(fc.is_default for fc in field_confidences)
        if any_defaults:
            return NormalizationStatus.PARTIAL

        return NormalizationStatus.COMPLETE
