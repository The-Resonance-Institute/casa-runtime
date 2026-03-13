"""
CASA UIA — Shim: CrewAI
========================
Extracts an IIO from CrewAI Task execution and AgentAction formats.

CrewAI is the cleanest Layer 3 proof because it carries native role
definitions, agent backstory, and crew hierarchy in every action.
These map directly to authorization_context without inference.

Architectural Law #1: Shims extract. They do not govern.

CrewAI formats handled:
  1. Task dict — {"description": ..., "agent": {"role": ..., "backstory": ...}}
  2. AgentAction dict — {"tool": ..., "tool_input": ..., "thought": ...}
  3. CrewAI object — any object with .tool, .tool_input, .agent attributes

(C) 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC
USPTO Provisional Patent #63/987,813
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from ..models import IntermediateIntentObject

logger = logging.getLogger(__name__)


class CrewAIShim:
    SOURCE_FRAMEWORK = "crewai"

    def extract(self, action, domain=None, caller_id=None):
        warnings = []
        action_dict = self._normalize(action, warnings)
        if self._is_task_format(action_dict):
            return self._extract_from_task(action_dict, domain, caller_id, warnings)
        else:
            return self._extract_from_agent_action(action_dict, domain, caller_id, warnings)

    def _extract_from_task(self, task, domain, caller_id, warnings):
        agent = task.get("agent") or {}
        if isinstance(agent, str):
            agent = {"role": agent}
        role = self._extract_role_from_agent(agent)
        backstory = agent.get("backstory", "")
        allow_delegation = agent.get("allow_delegation", False)
        crew_hierarchy = task.get("crew_hierarchy") or []
        tools = task.get("tools") or []
        tool_name = tools[0] if tools else self._infer_tool_from_description(
            task.get("description", ""), warnings)
        context = task.get("context") or {}
        tool_args = context if isinstance(context, dict) else {}
        auth_ctx = self._build_auth_context(role, backstory, allow_delegation,
                                            crew_hierarchy, tool_args,
                                            task.get("description", ""))
        return IntermediateIntentObject(
            source_framework=self.SOURCE_FRAMEWORK,
            raw_request_id=task.get("id") or task.get("task_id"),
            raw_tool_name=tool_name,
            raw_tool_args=tool_args,
            raw_caller_id=caller_id or agent.get("id") or agent.get("name"),
            raw_caller_role=role,
            raw_authorization_context=auth_ctx,
            raw_target_resource=self._extract_string(tool_args, ["resource_type", "target", "object_type"]),
            raw_target_id=self._extract_string(tool_args, ["id", "record_id", "account_id"]),
            raw_amount=self._extract_numeric(tool_args, ["amount", "value", "sum", "transfer_amount"]),
            raw_record_count=self._extract_int(tool_args, ["count", "limit", "n"]),
            raw_currency=self._extract_string(tool_args, ["currency", "currency_code"]),
            raw_approval_tokens=self._extract_approval_tokens(tool_args, auth_ctx),
            raw_priority_flag=self._extract_string(tool_args, ["priority", "urgency"]),
            raw_domain=domain,
            raw_scope_qualifier=self._extract_scope_qualifier(tool_args, task.get("description", "")),
            extraction_warnings=warnings,
            extraction_timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _extract_from_agent_action(self, action, domain, caller_id, warnings):
        tool_name = action.get("tool") or action.get("action") or action.get("name")
        tool_args = self._extract_tool_args(action, warnings)
        agent = action.get("agent")
        role = (action.get("agent_role") or action.get("role") or
                (agent.get("role") if isinstance(agent, dict) else None))
        if role:
            role = str(role)
        crew_hierarchy = action.get("crew_hierarchy") or []
        backstory = (action.get("backstory") or
                     (agent.get("backstory") if isinstance(agent, dict) else "") or "")
        auth_ctx = self._build_auth_context(role, backstory,
                                            action.get("allow_delegation", False),
                                            crew_hierarchy, tool_args,
                                            action.get("thought", "") or action.get("description", ""))
        return IntermediateIntentObject(
            source_framework=self.SOURCE_FRAMEWORK,
            raw_request_id=action.get("id") or action.get("run_id"),
            raw_tool_name=tool_name,
            raw_tool_args=tool_args,
            raw_caller_id=caller_id or action.get("agent_id") or action.get("agent_name"),
            raw_caller_role=role,
            raw_authorization_context=auth_ctx,
            raw_target_resource=self._extract_string(tool_args, ["resource_type", "target", "object_type"]),
            raw_target_id=self._extract_string(tool_args, ["id", "record_id", "account_id"]),
            raw_amount=self._extract_numeric(tool_args, ["amount", "value", "sum", "transfer_amount"]),
            raw_record_count=self._extract_int(tool_args, ["count", "limit", "n"]),
            raw_currency=self._extract_string(tool_args, ["currency", "currency_code"]),
            raw_approval_tokens=self._extract_approval_tokens(tool_args, auth_ctx),
            raw_priority_flag=self._extract_string(tool_args, ["priority", "urgency"]),
            raw_domain=domain,
            raw_scope_qualifier=self._extract_scope_qualifier(tool_args, action.get("thought", "") or ""),
            extraction_warnings=warnings,
            extraction_timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _build_auth_context(self, role, backstory, allow_delegation,
                             crew_hierarchy, tool_args, task_description):
        auth_ctx = {}
        if role:
            auth_ctx["role"] = role.lower().replace(" ", "_")
            auth_ctx["role_display"] = role
        if backstory:
            auth_ctx["backstory"] = backstory
            spending_limit = self._parse_spending_limit_from_text(backstory)
            if spending_limit:
                auth_ctx["spending_limit"] = spending_limit
        if allow_delegation:
            auth_ctx["allow_delegation"] = True
        if crew_hierarchy:
            auth_ctx["crew_hierarchy"] = crew_hierarchy
            auth_ctx["delegation_depth"] = len(crew_hierarchy) - 1 if len(crew_hierarchy) > 1 else 0
            if role and role in crew_hierarchy:
                auth_ctx["hierarchy_position"] = crew_hierarchy.index(role)
        if "spending_limit" not in auth_ctx:
            limit = self._extract_numeric(tool_args, ["spending_limit", "authority_limit", "max_amount"])
            if limit:
                auth_ctx["spending_limit"] = limit
        desc_lower = (task_description + " " + backstory).lower()
        if any(s in desc_lower for s in ["approved", "pre-approved", "board approved"]):
            auth_ctx["workflow_state"] = "approved"
        elif any(s in desc_lower for s in ["pending approval", "awaiting approval"]):
            auth_ctx["workflow_state"] = "pending_approval"
        return auth_ctx

    @staticmethod
    def _normalize(action, warnings):
        if isinstance(action, dict):
            return action
        result = {}
        for attr in ("description", "expected_output", "agent", "tools", "context",
                     "tool", "tool_input", "thought", "agent_role", "crew_hierarchy",
                     "backstory", "allow_delegation", "id", "task_id", "run_id",
                     "name", "role", "action", "action_input"):
            if hasattr(action, attr):
                result[attr] = getattr(action, attr)
        if not result:
            warnings.append(f"Could not normalize CrewAI action of type {type(action).__name__}")
        return result

    @staticmethod
    def _is_task_format(action):
        return ("description" in action and "agent" in action) or \
               ("tools" in action and "expected_output" in action)

    @staticmethod
    def _extract_role_from_agent(agent):
        for key in ("role", "title", "position", "job_title"):
            if key in agent and isinstance(agent[key], str):
                return agent[key]
        return None

    @staticmethod
    def _extract_tool_args(action, warnings):
        if "tool_input" in action:
            val = action["tool_input"]
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except json.JSONDecodeError:
                    return {"input": val}
            elif isinstance(val, dict):
                return val
        if "action_input" in action:
            val = action["action_input"]
            if isinstance(val, dict):
                return val
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except json.JSONDecodeError:
                    return {"input": val}
        if "args" in action and isinstance(action["args"], dict):
            return action["args"]
        if "context" in action and isinstance(action["context"], dict):
            return action["context"]
        return {}

    @staticmethod
    def _infer_tool_from_description(description, warnings):
        desc_lower = description.lower()
        signals = {
            "transfer": "transfer_funds", "wire": "wire_transfer",
            "delete": "delete_record", "remove": "delete_record",
            "create": "create_record", "update": "update_record",
            "query": "query_database", "search": "search_records",
            "send email": "send_email", "escalate": "escalate_ticket",
            "deploy": "deploy_code", "execute": "run_script",
        }
        for signal, tool in signals.items():
            if signal in desc_lower:
                warnings.append(f"tool_name inferred: '{signal}' -> '{tool}'")
                return tool
        warnings.append("Could not infer tool_name from task description")
        return None

    @staticmethod
    def _parse_spending_limit_from_text(text):
        patterns = [
            r'up to \$([0-9,]+(?:\.[0-9]+)?)',
            r'limit of \$([0-9,]+(?:\.[0-9]+)?)',
            r'authority.*?\$([0-9,]+(?:\.[0-9]+)?)',
            r'\$([0-9,]+(?:\.[0-9]+)?)\s*spending',
        ]
        text_lower = text.lower()
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                raw = match.group(1).replace(",", "")
                try:
                    value = float(raw)
                    ctx = text_lower[max(0, match.start()-5):match.end()+10]
                    if "thousand" in ctx or re.search(r'\bk\b', ctx):
                        value *= 1_000
                    elif "million" in ctx or re.search(r'\bm\b', ctx):
                        value *= 1_000_000
                    return value
                except ValueError:
                    pass
        return None

    @staticmethod
    def _extract_numeric(args, keys):
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
    def _extract_int(args, keys):
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
    def _extract_string(args, keys):
        if not args:
            return None
        for key in keys:
            if key in args and isinstance(args[key], str):
                return args[key]
        return None

    @staticmethod
    def _extract_approval_tokens(args, auth_ctx):
        tokens = []
        token_keys = ["approval_token", "approval_tokens", "consent_token", "auth_token"]
        for source in (args, auth_ctx):
            if not source:
                continue
            for key in token_keys:
                if key in source:
                    val = source[key]
                    if isinstance(val, str) and val.strip():
                        tokens.append(val)
                    elif isinstance(val, list):
                        tokens.extend([str(t) for t in val if t and str(t).strip()])
        return tokens

    @staticmethod
    def _extract_scope_qualifier(args, description):
        if args:
            for key in ("scope", "filter", "target_id", "id"):
                if key in args and isinstance(args[key], (str, int)):
                    return str(args[key])
        desc_lower = description.lower()
        for signal in ("all ", "entire ", "every ", "portfolio-wide", "fund-wide"):
            if signal in desc_lower:
                return "all"
        return None
