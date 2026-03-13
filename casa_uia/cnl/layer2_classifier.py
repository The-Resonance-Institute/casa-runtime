"""
CASA UIA — CNL Layer 2: Semantic Classifier
============================================
Resolves action_class, target_class, scope, magnitude, timing, and reversibility
from normalized Layer 1 fields using the three registry files.

This is the classification engine. It uses registry lookups and threshold
comparisons. It does NOT perform authority resolution — that is Layer 3.

Conservative defaults apply whenever confidence falls below threshold or
fields are absent.

© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..models import (
    ActionClass, FieldConfidence, Magnitude, NormalizationMetadata,
    NormalizationStatus, Reversibility, Scope, TargetClass, Timing,
)
from .layer1_extractor import Layer1Output

logger = logging.getLogger(__name__)

# Registry paths
_REGISTRY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "registries")
_ACTION_REGISTRY_PATH = os.path.join(_REGISTRY_DIR, "action_class_registry.json")
_TARGET_REGISTRY_PATH = os.path.join(_REGISTRY_DIR, "target_pattern_registry.json")
_THRESHOLDS_PATH = os.path.join(_REGISTRY_DIR, "domain_thresholds.json")

# Confidence threshold below which status becomes AMBIGUOUS
AMBIGUITY_THRESHOLD = 0.75


@dataclass
class Layer2Output:
    """Six of the nine CAV fields resolved by Layer 2."""
    action_class: ActionClass
    target_class: TargetClass
    scope: Scope
    magnitude: Magnitude
    timing: Timing
    reversibility: Reversibility
    field_confidences: List[FieldConfidence]


class SemanticClassifier:
    """
    Layer 2: Registry-based classification.

    Loads registries once at instantiation. Thread-safe for reads.
    """

    def __init__(self):
        self._action_registry = self._load_json(_ACTION_REGISTRY_PATH)
        self._target_registry = self._load_json(_TARGET_REGISTRY_PATH)
        self._thresholds = self._load_json(_THRESHOLDS_PATH)
        logger.debug("Layer 2 registries loaded")

    def classify(
        self,
        layer1: Layer1Output,
        metadata: NormalizationMetadata,
    ) -> Layer2Output:
        metadata.add_trace("Layer 2: Semantic classification begin")

        field_confidences: List[FieldConfidence] = []

        # ── action_class ─────────────────────────────────────────────
        action_class, action_confidence = self._resolve_action_class(
            layer1.tool_name_normalized, metadata
        )
        field_confidences.append(FieldConfidence(
            field_name="action_class",
            value=action_class,
            confidence=action_confidence,
            derivation=f"Registry lookup: '{layer1.tool_name_normalized}' → {action_class.value}",
            is_default=(action_confidence < 0.50),
            assumption="No registry match — defaulted to EXECUTE (conservative)" if action_confidence < 0.50 else None,
        ))

        # ── target_class ──────────────────────────────────────────────
        target_class, target_confidence = self._resolve_target_class(
            layer1.target_resource_normalized, metadata
        )
        field_confidences.append(FieldConfidence(
            field_name="target_class",
            value=target_class,
            confidence=target_confidence,
            derivation=f"Pattern match: '{layer1.target_resource_normalized}' → {target_class.value}",
            is_default=(target_confidence < 0.50),
            assumption="No pattern match — defaulted to SYSTEM (conservative)" if target_confidence < 0.50 else None,
        ))

        # ── scope ─────────────────────────────────────────────────────
        domain = layer1.domain or "default"
        scope, scope_confidence = self._resolve_scope(
            layer1.record_count,
            layer1.scope_qualifier,
            layer1.tool_args,
            domain,
            metadata,
        )
        field_confidences.append(FieldConfidence(
            field_name="scope",
            value=scope,
            confidence=scope_confidence,
            derivation=self._scope_derivation(
                layer1.record_count, layer1.scope_qualifier, scope
            ),
            is_default=(scope_confidence < 0.60),
            assumption="Scope signals absent — defaulted to UNBOUNDED (conservative)" if scope_confidence < 0.60 else None,
        ))

        # ── magnitude ─────────────────────────────────────────────────
        magnitude, magnitude_confidence = self._resolve_magnitude(
            layer1.amount,
            layer1.record_count,
            domain,
            metadata,
        )
        field_confidences.append(FieldConfidence(
            field_name="magnitude",
            value=magnitude,
            confidence=magnitude_confidence,
            derivation=self._magnitude_derivation(layer1.amount, layer1.record_count, magnitude, domain),
            is_default=(magnitude_confidence < 0.60),
            assumption="Magnitude signals absent — defaulted to CRITICAL (conservative)" if magnitude_confidence < 0.60 else None,
        ))

        # ── timing ───────────────────────────────────────────────────
        timing, timing_confidence = self._resolve_timing(
            layer1.priority_flag, layer1.tool_args, metadata
        )
        field_confidences.append(FieldConfidence(
            field_name="timing",
            value=timing,
            confidence=timing_confidence,
            derivation=f"Priority signal: '{layer1.priority_flag}' → {timing.value}",
        ))

        # ── reversibility ─────────────────────────────────────────────
        reversibility, rev_confidence = self._resolve_reversibility(
            action_class, layer1.tool_name_normalized, metadata
        )
        field_confidences.append(FieldConfidence(
            field_name="reversibility",
            value=reversibility,
            confidence=rev_confidence,
            derivation=f"Action+tool signal: {action_class.value} / '{layer1.tool_name_normalized}' → {reversibility.value}",
            is_default=(rev_confidence < 0.60),
            assumption="Reversibility unclear — defaulted to IRREVERSIBLE (conservative)" if rev_confidence < 0.60 else None,
        ))

        # ── Check for ambiguity ───────────────────────────────────────
        low_confidence_fields = [
            fc for fc in field_confidences
            if fc.confidence < AMBIGUITY_THRESHOLD
        ]
        if low_confidence_fields:
            field_names = [fc.field_name for fc in low_confidence_fields]
            metadata.add_warning(
                f"Low confidence on fields {field_names} — normalization status: AMBIGUOUS"
            )

        metadata.add_trace("Layer 2: Semantic classification complete")

        return Layer2Output(
            action_class=action_class,
            target_class=target_class,
            scope=scope,
            magnitude=magnitude,
            timing=timing,
            reversibility=reversibility,
            field_confidences=field_confidences,
        )

    # ── action_class resolution ─────────────────────────────────────

    def _resolve_action_class(
        self, tool_name: Optional[str], metadata: NormalizationMetadata
    ) -> Tuple[ActionClass, float]:
        if not tool_name:
            metadata.add_assumption("tool_name absent — action_class defaulted to EXECUTE")
            return ActionClass.EXECUTE, 0.30

        # Exact match first
        entry = self._action_registry.get(tool_name)
        if entry:
            ac = ActionClass(entry["action_class"])
            confidence = entry["confidence"]
            metadata.add_trace(f"Layer 2: action_class exact match '{tool_name}' → {ac.value} ({confidence:.2f})")
            return ac, confidence

        # Substring match — check if any registry key is contained in the tool name
        best_match = None
        best_confidence = 0.0
        best_class = None
        for key, entry in self._action_registry.items():
            if key.startswith("_"):
                continue
            if key in tool_name or tool_name in key:
                # Prefer longer (more specific) matches
                if len(key) > len(best_match or ""):
                    best_match = key
                    best_confidence = entry["confidence"] * 0.90  # Penalize partial matches
                    best_class = ActionClass(entry["action_class"])

        if best_class:
            metadata.add_trace(
                f"Layer 2: action_class partial match '{tool_name}' via '{best_match}' → {best_class.value} ({best_confidence:.2f})"
            )
            return best_class, best_confidence

        # No match — conservative default
        metadata.add_assumption(
            f"tool_name '{tool_name}' not in registry — action_class defaulted to EXECUTE (conservative)"
        )
        return ActionClass.EXECUTE, 0.30

    # ── target_class resolution ─────────────────────────────────────

    def _resolve_target_class(
        self, target_resource: Optional[str], metadata: NormalizationMetadata
    ) -> Tuple[TargetClass, float]:
        if not target_resource:
            metadata.add_assumption("target_resource absent — target_class defaulted to SYSTEM (conservative)")
            return TargetClass.SYSTEM, 0.30

        patterns = self._target_registry.get("patterns", [])

        # Sort by pattern length descending — prefer specific matches
        patterns_sorted = sorted(patterns, key=lambda p: len(p["pattern"]), reverse=True)

        for entry in patterns_sorted:
            if entry["pattern"] in target_resource or target_resource in entry["pattern"]:
                tc = TargetClass(entry["target_class"])
                confidence = entry["confidence"]
                metadata.add_trace(
                    f"Layer 2: target_class match '{target_resource}' via '{entry['pattern']}' → {tc.value} ({confidence:.2f})"
                )
                return tc, confidence

        # No match
        metadata.add_assumption(
            f"target_resource '{target_resource}' has no pattern match — target_class defaulted to SYSTEM (conservative)"
        )
        return TargetClass.SYSTEM, 0.30

    # ── scope resolution ────────────────────────────────────────────

    def _resolve_scope(
        self,
        record_count: Optional[int],
        scope_qualifier: Optional[str],
        tool_args: Optional[Dict[str, Any]],
        domain: str,
        metadata: NormalizationMetadata,
    ) -> Tuple[Scope, float]:
        thresholds = self._get_domain_thresholds(domain)
        record_thresholds = thresholds.get("record_count", {})
        unbounded_signals = record_thresholds.get("unbounded_keyword_signals", [])
        bounded_threshold = record_thresholds.get("bounded_threshold", 1000)

        # Check scope qualifier for explicit unbounded signals
        if scope_qualifier:
            for signal in unbounded_signals:
                if signal in scope_qualifier:
                    metadata.add_trace(
                        f"Layer 2: scope UNBOUNDED — qualifier '{scope_qualifier}' matches signal '{signal}'"
                    )
                    return Scope.UNBOUNDED, 0.90

        # Check tool_args for unbounded signals
        if tool_args:
            args_str = json.dumps(tool_args).lower()
            for signal in unbounded_signals:
                if signal in args_str:
                    metadata.add_trace(
                        f"Layer 2: scope UNBOUNDED — tool_args contain unbounded signal '{signal}'"
                    )
                    return Scope.UNBOUNDED, 0.85

        # Record count resolution
        if record_count is not None:
            if record_count == 1:
                metadata.add_trace(f"Layer 2: scope SINGLE — record_count=1")
                return Scope.SINGLE, 0.95
            elif record_count <= bounded_threshold:
                metadata.add_trace(f"Layer 2: scope BOUNDED — record_count={record_count} <= {bounded_threshold}")
                return Scope.BOUNDED, 0.90
            else:
                metadata.add_trace(f"Layer 2: scope UNBOUNDED — record_count={record_count} > {bounded_threshold}")
                return Scope.UNBOUNDED, 0.90

        # Check for a specific target_id (SINGLE implied)
        if scope_qualifier and re.search(r'\d', scope_qualifier):
            metadata.add_trace(f"Layer 2: scope SINGLE — scope_qualifier contains ID '{scope_qualifier}'")
            return Scope.SINGLE, 0.80

        # Conservative default
        metadata.add_assumption("scope signals absent — defaulted to UNBOUNDED (conservative)")
        return Scope.UNBOUNDED, 0.40

    # ── magnitude resolution ─────────────────────────────────────────

    def _resolve_magnitude(
        self,
        amount: Optional[float],
        record_count: Optional[int],
        domain: str,
        metadata: NormalizationMetadata,
    ) -> Tuple[Magnitude, float]:
        thresholds = self._get_domain_thresholds(domain)
        mag_thresholds = thresholds.get("magnitude", {})
        material_threshold = mag_thresholds.get("material_threshold", 1000)
        critical_threshold = mag_thresholds.get("critical_threshold", 100000)

        if amount is not None:
            if amount >= critical_threshold:
                metadata.add_trace(
                    f"Layer 2: magnitude CRITICAL — amount {amount} >= critical threshold {critical_threshold}"
                )
                return Magnitude.CRITICAL, 0.95
            elif amount >= material_threshold:
                metadata.add_trace(
                    f"Layer 2: magnitude MATERIAL — amount {amount} >= material threshold {material_threshold}"
                )
                return Magnitude.MATERIAL, 0.95
            else:
                metadata.add_trace(
                    f"Layer 2: magnitude TRIVIAL — amount {amount} < material threshold {material_threshold}"
                )
                return Magnitude.TRIVIAL, 0.90

        # Conservative default
        metadata.add_assumption("magnitude signals absent — defaulted to CRITICAL (conservative)")
        return Magnitude.CRITICAL, 0.40

    # ── timing resolution ────────────────────────────────────────────

    def _resolve_timing(
        self,
        priority_flag: Optional[str],
        tool_args: Optional[Dict[str, Any]],
        metadata: NormalizationMetadata,
    ) -> Tuple[Timing, float]:
        timing_signals = self._thresholds.get("timing_signals", {})

        signal = priority_flag or ""
        if tool_args:
            signal = signal + " " + json.dumps(tool_args).lower()

        for immediate_signal in timing_signals.get("IMMEDIATE", []):
            if immediate_signal in signal:
                metadata.add_trace(f"Layer 2: timing IMMEDIATE — signal '{immediate_signal}' found")
                return Timing.IMMEDIATE, 0.85

        for expedited_signal in timing_signals.get("EXPEDITED", []):
            if expedited_signal in signal:
                metadata.add_trace(f"Layer 2: timing EXPEDITED — signal '{expedited_signal}' found")
                return Timing.EXPEDITED, 0.85

        # Default to ROUTINE — not conservative because ROUTINE is the safe baseline
        metadata.add_trace("Layer 2: timing ROUTINE — no urgency signals")
        return Timing.ROUTINE, 0.90

    # ── reversibility resolution ─────────────────────────────────────

    def _resolve_reversibility(
        self,
        action_class: ActionClass,
        tool_name: Optional[str],
        metadata: NormalizationMetadata,
    ) -> Tuple[Reversibility, float]:
        rev_signals = self._thresholds.get("reversibility_signals", {})

        probe = f"{action_class.value.lower()} {tool_name or ''}"

        for signal in rev_signals.get("IRREVERSIBLE", []):
            if signal in probe:
                metadata.add_trace(
                    f"Layer 2: reversibility IRREVERSIBLE — signal '{signal}' in action/tool probe"
                )
                return Reversibility.IRREVERSIBLE, 0.90

        for signal in rev_signals.get("COSTLY", []):
            if signal in probe:
                metadata.add_trace(
                    f"Layer 2: reversibility COSTLY — signal '{signal}' in action/tool probe"
                )
                return Reversibility.COSTLY, 0.85

        if action_class in (ActionClass.QUERY,):
            metadata.add_trace("Layer 2: reversibility REVERSIBLE — QUERY action")
            return Reversibility.REVERSIBLE, 0.95

        if action_class in (ActionClass.TRANSFER,):
            metadata.add_trace("Layer 2: reversibility IRREVERSIBLE — TRANSFER action defaults to irreversible")
            return Reversibility.IRREVERSIBLE, 0.85

        if action_class in (ActionClass.CREATE, ActionClass.MODIFY):
            metadata.add_trace("Layer 2: reversibility REVERSIBLE — CREATE/MODIFY default")
            return Reversibility.REVERSIBLE, 0.80

        # Conservative default
        metadata.add_assumption("reversibility unclear — defaulted to IRREVERSIBLE (conservative)")
        return Reversibility.IRREVERSIBLE, 0.50

    # ── Helpers ──────────────────────────────────────────────────────

    def _get_domain_thresholds(self, domain: str) -> Dict[str, Any]:
        domains = self._thresholds.get("domains", {})
        return domains.get(domain, domains.get("default", {}))

    @staticmethod
    def _scope_derivation(
        record_count: Optional[int], scope_qualifier: Optional[str], scope: Scope
    ) -> str:
        if record_count is not None:
            return f"record_count={record_count} → {scope.value}"
        if scope_qualifier:
            return f"scope_qualifier='{scope_qualifier}' → {scope.value}"
        return f"No scope signals — conservative default → {scope.value}"

    @staticmethod
    def _magnitude_derivation(
        amount: Optional[float],
        record_count: Optional[int],
        magnitude: Magnitude,
        domain: str,
    ) -> str:
        if amount is not None:
            return f"amount={amount} ({domain} domain) → {magnitude.value}"
        if record_count is not None:
            return f"record_count={record_count} ({domain} domain) → {magnitude.value}"
        return f"No magnitude signals ({domain} domain) — conservative default → {magnitude.value}"

    @staticmethod
    def _load_json(path: str) -> Dict:
        with open(path, "r") as f:
            return json.load(f)
