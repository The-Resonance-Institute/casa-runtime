"""
CASA UIA — Shim: OpenAI Tool Call
==================================
Extracts an IIO from an OpenAI Chat Completions tool call object.

Handles both the legacy function_call format and the current tool_calls
list format. Extracts only — no governance logic.

Architectural Law #1: Shims extract. They do not govern.

OpenAI tool call format reference:
  https://platform.openai.com/docs/guides/function-calling

© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models import IntermediateIntentObject

logger = logging.getLogger(__name__)


class OpenAIToolCallShim:
    """
    Shim for OpenAI Chat Completions tool call format.

    Accepts either:
    1. A single tool call object from the tool_calls list:
       {
         "id": "call_abc123",
         "type": "function",
         "function": {
           "name": "transfer_funds",
           "arguments": "{\"amount\": 15000000, \"recipient\": \"LP-001\"}"
         }
       }

    2. The full message object containing tool_calls:
       {
         "role": "assistant",
         "tool_calls": [...]
       }

    3. The legacy function_call format:
       {
         "function_call": {
           "name": "transfer_funds",
           "arguments": "{...}"
         }
       }

    Authorization context is passed separately, as OpenAI tool calls
    do not carry auth context natively — it must come from the calling system.
    """

    SOURCE_FRAMEWORK = "openai_tool_call"

    def extract(
        self,
        tool_call: Dict[str, Any],
        authorization_context: Optional[Dict[str, Any]] = None,
        caller_id: Optional[str] = None,
        caller_role: Optional[str] = None,
        domain: Optional[str] = None,
        tool_call_index: int = 0,
    ) -> IntermediateIntentObject:
        """
        Extract IIO from an OpenAI tool call.

        Args:
            tool_call: OpenAI tool call object (single call or full message)
            authorization_context: Auth context from the calling system
            caller_id: Identity of the agent making the call
            caller_role: Role of the agent or user
            domain: Domain hint (e.g., "pe_fund", "financial")
            tool_call_index: If tool_calls is a list, which index to use

        Returns:
            IntermediateIntentObject ready for CNL normalization
        """
        warnings: List[str] = []

        # ── Locate the actual tool call object ───────────────────────
        actual_call = self._locate_tool_call(tool_call, tool_call_index, warnings)

        # ── Extract tool name ─────────────────────────────────────────
        tool_name, tool_args = self._extract_function(actual_call, warnings)

        # ── Extract target resource from tool_args ───────────────────
        # OpenAI tool calls don't have an explicit target field —
        # Layer 1 will attempt to infer from tool_args
        target_resource = self._extract_target_resource(tool_name, tool_args)

        # ── Extract numeric signals ───────────────────────────────────
        amount = self._extract_numeric(tool_args, ["amount", "value", "sum", "transfer_amount", "quantity"])
        record_count = self._extract_int(tool_args, ["count", "limit", "n", "num_records"])
        currency = self._extract_string(tool_args, ["currency", "currency_code"])

        # ── Extract approval tokens ───────────────────────────────────
        approval_tokens = self._extract_approval_tokens(tool_args, authorization_context)

        # ── Extract scope qualifier ───────────────────────────────────
        scope_qualifier = self._extract_scope_qualifier(tool_args)

        # ── Extract priority ──────────────────────────────────────────
        priority_flag = self._extract_string(tool_args, ["priority", "urgency"])

        # ── Request ID ────────────────────────────────────────────────
        request_id = actual_call.get("id") if actual_call else None

        iio = IntermediateIntentObject(
            source_framework=self.SOURCE_FRAMEWORK,
            raw_request_id=request_id,
            raw_tool_name=tool_name,
            raw_tool_args=tool_args,
            raw_caller_id=caller_id,
            raw_caller_role=caller_role,
            raw_authorization_context=authorization_context,
            raw_target_resource=target_resource,
            raw_target_id=self._extract_string(tool_args, ["id", "record_id", "user_id", "account_id", "resource_id"]),
            raw_amount=amount,
            raw_record_count=record_count,
            raw_currency=currency,
            raw_approval_tokens=approval_tokens,
            raw_priority_flag=priority_flag,
            raw_domain=domain,
            raw_scope_qualifier=scope_qualifier,
            extraction_warnings=warnings,
            extraction_timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return iio

    # ── Internal helpers ────────────────────────────────────────────

    def _locate_tool_call(
        self,
        tool_call: Dict[str, Any],
        index: int,
        warnings: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Find the actual tool call dict regardless of input format."""

        # Full message with tool_calls list
        if "tool_calls" in tool_call:
            calls = tool_call["tool_calls"]
            if not calls:
                warnings.append("tool_calls list is empty")
                return None
            if index >= len(calls):
                warnings.append(
                    f"tool_call_index {index} out of range (list has {len(calls)}); using 0"
                )
                index = 0
            return calls[index]

        # Legacy function_call format
        if "function_call" in tool_call:
            return tool_call

        # Already a single tool call object
        if "function" in tool_call or "id" in tool_call:
            return tool_call

        warnings.append("Could not locate tool call in input — returning as-is")
        return tool_call

    @staticmethod
    def _extract_function(
        call: Optional[Dict[str, Any]], warnings: List[str]
    ):
        """Extract function name and parsed arguments."""
        if not call:
            return None, {}

        # Standard format: call.function.name + call.function.arguments
        func = call.get("function") or call.get("function_call")
        if func and isinstance(func, dict):
            name = func.get("name")
            raw_args = func.get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    warnings.append(f"Could not parse function arguments as JSON: {raw_args[:100]}")
                    args = {}
            elif isinstance(raw_args, dict):
                args = raw_args
            else:
                args = {}
            return name, args

        warnings.append("No 'function' or 'function_call' key found in tool call")
        return None, {}

    @staticmethod
    def _extract_target_resource(
        tool_name: Optional[str], tool_args: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Attempt to identify the target resource type.
        OpenAI tool calls embed target info in the tool name or arguments.
        """
        if not tool_name:
            return None

        # Many tool names follow: {verb}_{resource_type}
        # e.g. transfer_funds → "funds", delete_user → "user", update_customer_record → "customer_record"
        parts = tool_name.split("_")
        if len(parts) >= 2:
            # Return everything after the first word (the verb)
            return "_".join(parts[1:])

        # Check tool_args for an explicit resource type
        if tool_args:
            for key in ("resource_type", "target", "object_type", "entity_type"):
                if key in tool_args and isinstance(tool_args[key], str):
                    return tool_args[key]

        return None

    @staticmethod
    def _extract_numeric(
        args: Optional[Dict[str, Any]], keys: List[str]
    ) -> Optional[float]:
        if not args:
            return None
        for key in keys:
            if key in args:
                try:
                    return float(args[key])
                except (TypeError, ValueError):
                    pass
        return None

    @staticmethod
    def _extract_int(
        args: Optional[Dict[str, Any]], keys: List[str]
    ) -> Optional[int]:
        if not args:
            return None
        for key in keys:
            if key in args:
                try:
                    return int(args[key])
                except (TypeError, ValueError):
                    pass
        return None

    @staticmethod
    def _extract_string(
        args: Optional[Dict[str, Any]], keys: List[str]
    ) -> Optional[str]:
        if not args:
            return None
        for key in keys:
            if key in args and isinstance(args[key], str):
                return args[key]
        return None

    @staticmethod
    def _extract_approval_tokens(
        args: Optional[Dict[str, Any]],
        auth_ctx: Optional[Dict[str, Any]],
    ) -> List[str]:
        tokens = []
        token_keys = ["approval_token", "approval_tokens", "consent_token", "auth_token"]
        for source in (args, auth_ctx):
            if not source:
                continue
            for key in token_keys:
                if key in source:
                    val = source[key]
                    if isinstance(val, str) and val:
                        tokens.append(val)
                    elif isinstance(val, list):
                        tokens.extend([str(t) for t in val if t])
        return tokens

    @staticmethod
    def _extract_scope_qualifier(args: Optional[Dict[str, Any]]) -> Optional[str]:
        """Extract scope qualifier — specific ID or unbounded signal."""
        if not args:
            return None
        for key in ("scope", "filter", "where", "all", "target_id", "id"):
            if key in args:
                val = args[key]
                if isinstance(val, (str, int)):
                    return str(val)
        return None
