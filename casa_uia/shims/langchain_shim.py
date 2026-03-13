"""
CASA UIA — Shim: LangChain
===========================
Extracts an IIO from LangChain AgentAction, tool call dict,
or StructuredTool invocation format.

Architectural Law #1: Shims extract. They do not govern.

LangChain formats handled:
  1. AgentAction: .tool + .tool_input
  2. Tool call dict: {"name": ..., "args": {...}}
  3. StructuredTool invocation: {"tool": ..., "tool_input": {...}}

© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from ..models import IntermediateIntentObject

logger = logging.getLogger(__name__)


class LangChainShim:
    """
    Shim for LangChain agent tool call formats.

    LangChain AgentAction example:
        {
          "tool": "transfer_funds",
          "tool_input": {
            "amount": 15000000,
            "recipient_account": "LP-ACCOUNT-001",
            "approval_token": "tok_abc123"
          },
          "log": "I need to transfer funds to the LP account."
        }

    LangChain tool call dict example:
        {
          "name": "transfer_funds",
          "args": {"amount": 15000000, "recipient_account": "LP-ACCOUNT-001"}
        }

    Authorization context must be passed separately.
    """

    SOURCE_FRAMEWORK = "langchain"

    def extract(
        self,
        agent_action: Union[Dict[str, Any], Any],
        authorization_context: Optional[Dict[str, Any]] = None,
        caller_id: Optional[str] = None,
        caller_role: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> IntermediateIntentObject:
        """
        Extract IIO from a LangChain agent action.

        Args:
            agent_action: LangChain AgentAction object or dict equivalent
            authorization_context: Auth context from the calling system
            caller_id: Agent identity
            caller_role: Agent role
            domain: Domain hint

        Returns:
            IntermediateIntentObject
        """
        warnings: List[str] = []

        # Normalize: handle both dataclass-style objects and dicts
        action_dict = self._normalize_agent_action(agent_action, warnings)

        # ── Extract tool name ─────────────────────────────────────────
        tool_name = self._extract_tool_name(action_dict, warnings)

        # ── Extract tool args ─────────────────────────────────────────
        tool_args = self._extract_tool_args(action_dict, warnings)

        # ── Target resource from tool name ────────────────────────────
        target_resource = self._extract_target_resource(tool_name)

        # ── Numeric signals ───────────────────────────────────────────
        amount = self._extract_numeric(tool_args, ["amount", "value", "sum", "transfer_amount"])
        record_count = self._extract_int(tool_args, ["count", "limit", "n", "num_records"])
        currency = self._extract_string(tool_args, ["currency", "currency_code"])

        # ── Approval tokens ───────────────────────────────────────────
        approval_tokens = self._extract_approval_tokens(tool_args, authorization_context)

        # ── Scope qualifier ───────────────────────────────────────────
        scope_qualifier = self._extract_scope_qualifier(tool_args)

        # ── Priority ─────────────────────────────────────────────────
        priority_flag = self._extract_string(tool_args, ["priority", "urgency", "timing"])

        iio = IntermediateIntentObject(
            source_framework=self.SOURCE_FRAMEWORK,
            raw_request_id=action_dict.get("run_id") or action_dict.get("id"),
            raw_tool_name=tool_name,
            raw_tool_args=tool_args,
            raw_caller_id=caller_id,
            raw_caller_role=caller_role,
            raw_authorization_context=authorization_context,
            raw_target_resource=target_resource,
            raw_target_id=self._extract_string(
                tool_args, ["id", "record_id", "account_id", "resource_id", "user_id"]
            ),
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

    @staticmethod
    def _normalize_agent_action(
        action: Any, warnings: List[str]
    ) -> Dict[str, Any]:
        """Convert AgentAction object or dict to a uniform dict."""
        if isinstance(action, dict):
            return action

        # Handle LangChain AgentAction dataclass/object
        result = {}
        for attr in ("tool", "tool_input", "log", "run_id", "name", "args"):
            if hasattr(action, attr):
                result[attr] = getattr(action, attr)

        if not result:
            warnings.append(f"Could not normalize agent_action of type {type(action).__name__}")
            return {}

        return result

    @staticmethod
    def _extract_tool_name(action: Dict[str, Any], warnings: List[str]) -> Optional[str]:
        """Extract tool name from action dict."""
        # LangChain AgentAction format
        if "tool" in action:
            return action["tool"]

        # LangChain tool call dict format
        if "name" in action:
            return action["name"]

        # OpenAI-compatible format within LangChain
        func = action.get("function")
        if func and isinstance(func, dict):
            return func.get("name")

        warnings.append("No tool name found in agent action")
        return None

    @staticmethod
    def _extract_tool_args(
        action: Dict[str, Any], warnings: List[str]
    ) -> Dict[str, Any]:
        """Extract tool arguments from action dict."""
        # LangChain AgentAction format
        if "tool_input" in action:
            tool_input = action["tool_input"]
            if isinstance(tool_input, str):
                try:
                    return json.loads(tool_input)
                except json.JSONDecodeError:
                    # Sometimes tool_input is a plain string (single-arg tools)
                    return {"input": tool_input}
            elif isinstance(tool_input, dict):
                return tool_input

        # LangChain tool call dict format
        if "args" in action:
            return action["args"] or {}

        # OpenAI-compatible format
        func = action.get("function")
        if func and isinstance(func, dict):
            raw_args = func.get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    return json.loads(raw_args)
                except json.JSONDecodeError:
                    warnings.append("Could not parse function arguments")
                    return {}
            return raw_args or {}

        return {}

    @staticmethod
    def _extract_target_resource(tool_name: Optional[str]) -> Optional[str]:
        """Infer target resource type from tool name."""
        if not tool_name:
            return None
        parts = tool_name.split("_")
        if len(parts) >= 2:
            return "_".join(parts[1:])
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
        if not args:
            return None
        for key in ("scope", "filter", "where", "target_id", "id", "all"):
            if key in args:
                val = args[key]
                if isinstance(val, (str, int)):
                    return str(val)
        return None
