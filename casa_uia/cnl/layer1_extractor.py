"""
CASA UIA — CNL Layer 1: Structural Extractor
=============================================
Validates IIO completeness and prepares fields for Layer 2 classification.

Architectural Law #1: Shims extract. They do not govern.
Architectural Law #2: The normalizer must never hallucinate completeness.

Layer 1 performs NO inference. It validates that the IIO contains enough
raw material for Layers 2 and 3 to work with. It normalizes string values
(lowercase, strip punctuation) for registry lookup. It does NOT assign
CAV values. That is Layer 2's job.

© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..models import IntermediateIntentObject, NormalizationMetadata, NormalizationStatus

logger = logging.getLogger(__name__)


@dataclass
class Layer1Output:
    """
    Cleaned and validated structural fields ready for Layer 2.
    All strings normalized to lowercase with punctuation stripped.
    """
    # Cleaned structural fields
    tool_name_normalized: Optional[str]
    target_resource_normalized: Optional[str]
    caller_id: Optional[str]
    caller_role: Optional[str]
    authorization_context: Optional[Dict[str, Any]]
    tool_args: Optional[Dict[str, Any]]
    target_id: Optional[str]

    # Numeric signals
    amount: Optional[float]
    record_count: Optional[int]
    currency: Optional[str]

    # Context signals
    approval_tokens: List[str]
    priority_flag: Optional[str]
    domain: Optional[str]
    scope_qualifier: Optional[str]

    # Viability
    has_tool_name: bool
    has_target: bool
    has_auth_context: bool

    # Layer 1 warnings
    warnings: List[str]


class StructuralExtractor:
    """
    Layer 1: Validates and normalizes IIO fields.

    No inference. No registry lookups. No governance.
    Output feeds directly into Layer 2.
    """

    # Minimum viability: must have at least a tool name to proceed
    MINIMUM_VIABLE_FIELDS = {"raw_tool_name"}

    def extract(
        self,
        iio: IntermediateIntentObject,
        metadata: NormalizationMetadata,
    ) -> Tuple[Optional[Layer1Output], bool]:
        """
        Validate and normalize IIO.

        Returns (Layer1Output, viable) tuple.
        If viable=False, normalization cannot proceed.
        """
        metadata.add_trace("Layer 1: Structural extraction begin")
        warnings = []

        # ── Minimum viability check ──────────────────────────────────
        if not iio.raw_tool_name or not str(iio.raw_tool_name).strip():
            metadata.add_error("IIO missing raw_tool_name — cannot determine action_class")
            metadata.normalization_status = NormalizationStatus.FAILED
            return None, False

        # ── Normalize tool name ──────────────────────────────────────
        tool_name_normalized = self._normalize_string(iio.raw_tool_name)
        metadata.add_trace(f"Layer 1: tool_name '{iio.raw_tool_name}' → '{tool_name_normalized}'")

        # ── Normalize target resource ────────────────────────────────
        target_resource_normalized = None
        if iio.raw_target_resource:
            target_resource_normalized = self._normalize_string(iio.raw_target_resource)
            metadata.add_trace(
                f"Layer 1: target_resource '{iio.raw_target_resource}' → '{target_resource_normalized}'"
            )
        else:
            # Try to extract target from tool_args
            target_from_args = self._extract_target_from_args(iio.raw_tool_args)
            if target_from_args:
                target_resource_normalized = self._normalize_string(target_from_args)
                warnings.append(
                    f"target_resource not set by shim; inferred '{target_resource_normalized}' from tool_args"
                )
                metadata.add_trace(
                    f"Layer 1: target_resource inferred from tool_args → '{target_resource_normalized}'"
                )
            else:
                # Try to infer from tool name: verb_target → take everything after verb
                target_from_name = self._extract_target_from_tool_name(tool_name_normalized)
                if target_from_name:
                    target_resource_normalized = target_from_name
                    warnings.append(
                        f"target_resource inferred from tool_name → '{target_resource_normalized}'"
                    )
                    metadata.add_trace(
                        f"Layer 1: target_resource inferred from tool_name → '{target_resource_normalized}'"
                    )
                else:
                    warnings.append("target_resource absent — Layer 2 will apply conservative default")
                    metadata.add_trace("Layer 1: target_resource absent")

        # ── Auth context ──────────────────────────────────────────────
        has_auth_context = bool(iio.raw_authorization_context)
        if not has_auth_context:
            warnings.append("authorization_context absent — Layer 3 will default to EXCEEDS_GRANT")
            metadata.add_trace("Layer 1: authorization_context absent")

        # ── Numeric signals ──────────────────────────────────────────
        amount = self._coerce_float(iio.raw_amount)
        if iio.raw_amount is not None and amount is None:
            warnings.append(f"raw_amount '{iio.raw_amount}' could not be parsed as float")

        record_count = self._coerce_int(iio.raw_record_count)
        if iio.raw_record_count is not None and record_count is None:
            warnings.append(f"raw_record_count '{iio.raw_record_count}' could not be parsed as int")

        # Also try to find amount/count in tool_args if not set directly
        if amount is None and iio.raw_tool_args:
            amount = self._extract_amount_from_args(iio.raw_tool_args)
            if amount is not None:
                metadata.add_trace(f"Layer 1: amount {amount} extracted from tool_args")

        if record_count is None and iio.raw_tool_args:
            record_count = self._extract_count_from_args(iio.raw_tool_args)
            if record_count is not None:
                metadata.add_trace(f"Layer 1: record_count {record_count} extracted from tool_args")

        # ── Approval tokens ──────────────────────────────────────────
        approval_tokens = iio.raw_approval_tokens or []
        if not approval_tokens and iio.raw_tool_args:
            approval_tokens = self._extract_tokens_from_args(iio.raw_tool_args)
            if approval_tokens:
                metadata.add_trace(
                    f"Layer 1: {len(approval_tokens)} approval token(s) found in tool_args"
                )

        # ── Priority / timing signal ──────────────────────────────────
        priority_flag = None
        if iio.raw_priority_flag:
            priority_flag = self._normalize_string(iio.raw_priority_flag)
        elif iio.raw_tool_args:
            priority_flag = self._extract_priority_from_args(iio.raw_tool_args)

        # ── Domain ───────────────────────────────────────────────────
        domain = None
        if iio.raw_domain:
            domain = self._normalize_string(iio.raw_domain)

        # ── Scope qualifier ──────────────────────────────────────────
        scope_qualifier = None
        if iio.raw_scope_qualifier:
            scope_qualifier = self._normalize_string(iio.raw_scope_qualifier)

        # ── Propagate shim warnings ──────────────────────────────────
        for w in iio.extraction_warnings:
            warnings.append(f"[shim] {w}")

        for w in warnings:
            metadata.add_warning(w)

        metadata.add_trace("Layer 1: Structural extraction complete")

        output = Layer1Output(
            tool_name_normalized=tool_name_normalized,
            target_resource_normalized=target_resource_normalized,
            caller_id=iio.raw_caller_id,
            caller_role=iio.raw_caller_role,
            authorization_context=iio.raw_authorization_context,
            tool_args=iio.raw_tool_args,
            target_id=iio.raw_target_id,
            amount=amount,
            record_count=record_count,
            currency=iio.raw_currency,
            approval_tokens=approval_tokens,
            priority_flag=priority_flag,
            domain=domain,
            scope_qualifier=scope_qualifier,
            has_tool_name=True,
            has_target=target_resource_normalized is not None,
            has_auth_context=has_auth_context,
            warnings=warnings,
        )

        return output, True

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _normalize_string(value: str) -> str:
        """Lowercase, replace non-alphanumeric with underscores, collapse runs."""
        if not value:
            return ""
        normalized = value.lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        normalized = normalized.strip("_")
        return normalized

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_target_from_tool_name(tool_name: str) -> Optional[str]:
        """
        Infer target resource from tool name.
        Pattern: verb_target → return target portion.
        e.g. 'delete_customer_record' → 'customer_record'
        """
        if not tool_name:
            return None
        parts = tool_name.split("_")
        if len(parts) >= 2:
            return "_".join(parts[1:])
        return None

    @staticmethod
    def _extract_target_from_args(args: Optional[Dict[str, Any]]) -> Optional[str]:
        """Try to find a target resource hint in tool arguments."""
        if not args:
            return None
        target_keys = [
            "target", "resource", "resource_type", "object_type", "entity",
            "record_type", "type", "object", "entity_type"
        ]
        for key in target_keys:
            if key in args and isinstance(args[key], str):
                return args[key]
        return None

    @staticmethod
    def _extract_amount_from_args(args: Dict[str, Any]) -> Optional[float]:
        """Try to find a numeric amount in tool arguments."""
        amount_keys = ["amount", "value", "sum", "total", "quantity", "price", "transfer_amount"]
        for key in amount_keys:
            if key in args:
                try:
                    return float(args[key])
                except (TypeError, ValueError):
                    pass
        return None

    @staticmethod
    def _extract_count_from_args(args: Dict[str, Any]) -> Optional[int]:
        """Try to find a record count in tool arguments."""
        count_keys = ["count", "limit", "n", "num_records", "batch_size", "records"]
        for key in count_keys:
            if key in args:
                try:
                    val = int(args[key])
                    # Sanity check — don't confuse amounts with counts
                    if val < 1_000_000:
                        return val
                except (TypeError, ValueError):
                    pass
        return None

    @staticmethod
    def _extract_tokens_from_args(args: Dict[str, Any]) -> List[str]:
        """Try to find approval tokens in tool arguments. Ignores empty/whitespace strings."""
        token_keys = ["approval_token", "approval_tokens", "consent_token", "authorization_token", "auth_token"]
        for key in token_keys:
            if key in args:
                val = args[key]
                if isinstance(val, str) and val.strip():
                    return [val]
                if isinstance(val, list):
                    return [str(t) for t in val if t and str(t).strip()]
        return []

    @staticmethod
    def _extract_priority_from_args(args: Dict[str, Any]) -> Optional[str]:
        """Try to find a priority flag in tool arguments."""
        priority_keys = ["priority", "urgency", "sla", "timing"]
        for key in priority_keys:
            if key in args and isinstance(args[key], str):
                return args[key].lower()
        return None
