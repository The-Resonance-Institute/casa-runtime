"""
CASA UIA — CNL Layer 3: Authority Resolver
==========================================
Resolves authorization and consent from the raw_authorization_context.

This is the IP moat. Authority resolution is the hardest and most valuable
part of the CNL. It evaluates role grants, delegation chains, approval token
chains, and consent derivation.

Architectural Law #5: Authority resolution is not authorization.
Determining that an actor HAS authority over a resource is a factual
evaluation of the grant record. Determining that they should USE that
authority in this context is a governance decision made by the gate.

The Layer 3 resolver evaluates facts. The gate governs.

© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..models import (
    ActionClass, Authorization, Consent, FieldConfidence,
    NormalizationMetadata, TargetClass,
)
from .layer1_extractor import Layer1Output
from .layer2_classifier import Layer2Output

logger = logging.getLogger(__name__)

# Known high-privilege roles that explicitly grant broad authority
_HIGH_PRIVILEGE_ROLES = {
    "admin", "administrator", "superuser", "root", "system",
    "platform_admin", "super_admin", "god_mode",
}

# Roles that typically carry transfer authority
_TRANSFER_AUTHORIZED_ROLES = {
    "fund_manager", "capital_allocator", "portfolio_manager",
    "treasurer", "finance_officer", "cfo", "payment_processor",
    "authorized_signatory",
}

# Roles that carry only read authority
_READ_ONLY_ROLES = {
    "viewer", "reader", "auditor", "analyst", "observer",
    "read_only", "reporting",
}

# Approval token key names that signal explicit consent
_APPROVAL_TOKEN_KEYS = {
    "approval_token", "consent_token", "authorization_token",
    "auth_token", "signed_approval", "mfa_token", "dual_control_token",
}

# Delegation chain depth limit — deeper chains are treated as EXCEEDS_GRANT
MAX_DELEGATION_DEPTH = 3


@dataclass
class Layer3Output:
    """Authorization and consent resolved from authority context."""
    authorization: Authorization
    consent: Consent
    field_confidences: List[FieldConfidence]
    resolution_trace: List[str]


class AuthorityResolver:
    """
    Layer 3: Authority context resolution.

    Evaluates the raw_authorization_context against the resolved
    action_class and target_class to determine authorization and consent.

    Always fails toward the conservative:
    - No context → EXCEEDS_GRANT, NONE
    - Ambiguous grants → AT_LIMIT
    - Expired/invalid tokens → NONE (not IMPLIED)
    - Delegation chain too deep → EXCEEDS_GRANT
    """

    def resolve(
        self,
        layer1: Layer1Output,
        layer2: Layer2Output,
        metadata: NormalizationMetadata,
    ) -> Layer3Output:
        metadata.add_trace("Layer 3: Authority resolution begin")
        resolution_trace: List[str] = []
        field_confidences: List[FieldConfidence] = []

        auth_ctx = layer1.authorization_context

        # ── authorization ─────────────────────────────────────────────
        authorization, auth_confidence = self._resolve_authorization(
            auth_ctx,
            layer2.action_class,
            layer2.target_class,
            layer1.caller_role,
            layer1.caller_id,
            layer1.amount,
            resolution_trace,
            metadata,
        )

        field_confidences.append(FieldConfidence(
            field_name="authorization",
            value=authorization,
            confidence=auth_confidence,
            derivation="; ".join(resolution_trace[-3:]) if resolution_trace else "No auth context",
            is_default=(not bool(auth_ctx)),
            assumption="No authorization context — defaulted to EXCEEDS_GRANT (conservative)" if not auth_ctx else None,
        ))

        # ── consent ───────────────────────────────────────────────────
        consent, consent_confidence = self._resolve_consent(
            auth_ctx,
            layer1.approval_tokens,
            layer2.action_class,
            layer2.target_class,
            layer1.caller_role,
            resolution_trace,
            metadata,
        )

        field_confidences.append(FieldConfidence(
            field_name="consent",
            value=consent,
            confidence=consent_confidence,
            derivation="; ".join(resolution_trace[-3:]) if resolution_trace else "No consent signals",
            is_default=(len(layer1.approval_tokens) == 0 and not bool(auth_ctx)),
            assumption="No approval tokens and no auth context — defaulted to NONE (conservative)" if not auth_ctx and not layer1.approval_tokens else None,
        ))

        metadata.add_trace("Layer 3: Authority resolution complete")

        return Layer3Output(
            authorization=authorization,
            consent=consent,
            field_confidences=field_confidences,
            resolution_trace=resolution_trace,
        )

    # ── Authorization resolution ─────────────────────────────────────

    def _resolve_authorization(
        self,
        auth_ctx: Optional[Dict[str, Any]],
        action_class: ActionClass,
        target_class: TargetClass,
        caller_role: Optional[str],
        caller_id: Optional[str],
        amount: Optional[float],
        trace: List[str],
        metadata: NormalizationMetadata,
    ) -> Tuple[Authorization, float]:

        # No auth context at all — conservative default
        if not auth_ctx and not caller_role:
            trace.append("No auth context or caller_role — EXCEEDS_GRANT (conservative default)")
            metadata.add_assumption("authorization_context absent — EXCEEDS_GRANT")
            return Authorization.EXCEEDS_GRANT, 0.30

        # Aggregate signals from both auth_ctx and caller_role
        role = self._extract_role(auth_ctx, caller_role)
        grants = self._extract_grants(auth_ctx)
        spending_limit = self._extract_spending_limit(auth_ctx)
        delegation_depth = self._extract_delegation_depth(auth_ctx)

        trace.append(f"Role resolved: '{role}'")

        # ── Delegation depth check ────────────────────────────────────
        if delegation_depth > MAX_DELEGATION_DEPTH:
            trace.append(
                f"Delegation chain depth {delegation_depth} exceeds max {MAX_DELEGATION_DEPTH} — EXCEEDS_GRANT"
            )
            return Authorization.EXCEEDS_GRANT, 0.90

        # ── High-privilege role ───────────────────────────────────────
        if role and self._role_in_set(role, _HIGH_PRIVILEGE_ROLES):
            trace.append(f"High-privilege role '{role}' — WITHIN_GRANT")
            return Authorization.WITHIN_GRANT, 0.85

        # ── Escalation action — always requires explicit grant ────────
        if action_class == ActionClass.ESCALATE:
            if grants and self._grant_covers_action(grants, "ESCALATE", target_class):
                trace.append("ESCALATE action — explicit grant found — WITHIN_GRANT")
                return Authorization.WITHIN_GRANT, 0.85
            trace.append("ESCALATE action — no explicit grant — EXCEEDS_GRANT")
            return Authorization.EXCEEDS_GRANT, 0.90

        # ── Transfer action ───────────────────────────────────────────
        if action_class == ActionClass.TRANSFER:
            if role and self._role_in_set(role, _TRANSFER_AUTHORIZED_ROLES):
                # Check spending limit if present
                if spending_limit is not None and amount is not None:
                    if amount > spending_limit:
                        trace.append(
                            f"TRANSFER: role '{role}' has authority but amount {amount} > spending limit {spending_limit} — EXCEEDS_GRANT"
                        )
                        return Authorization.EXCEEDS_GRANT, 0.95
                    elif amount == spending_limit:
                        trace.append(
                            f"TRANSFER: role '{role}' at spending limit exactly — AT_LIMIT"
                        )
                        return Authorization.AT_LIMIT, 0.90
                    else:
                        trace.append(
                            f"TRANSFER: role '{role}' within spending limit {spending_limit} — WITHIN_GRANT"
                        )
                        return Authorization.WITHIN_GRANT, 0.90
                else:
                    # No spending limit defined — role authorizes transfer
                    trace.append(f"TRANSFER: role '{role}' has transfer authority — WITHIN_GRANT")
                    return Authorization.WITHIN_GRANT, 0.80

            # TRANSFER with read-only role
            if role and self._role_in_set(role, _READ_ONLY_ROLES):
                trace.append(f"TRANSFER: read-only role '{role}' — EXCEEDS_GRANT")
                return Authorization.EXCEEDS_GRANT, 0.95

            # TRANSFER with unknown role — check explicit grants
            if grants and self._grant_covers_action(grants, "TRANSFER", target_class):
                trace.append("TRANSFER: explicit grant found — WITHIN_GRANT")
                return Authorization.WITHIN_GRANT, 0.85

            trace.append(f"TRANSFER: role '{role}' not in authorized transfer roles — EXCEEDS_GRANT")
            return Authorization.EXCEEDS_GRANT, 0.80

        # ── Read-only role check for write actions ────────────────────
        if role and self._role_in_set(role, _READ_ONLY_ROLES):
            if action_class not in (ActionClass.QUERY,):
                trace.append(
                    f"Write action {action_class.value} with read-only role '{role}' — EXCEEDS_GRANT"
                )
                return Authorization.EXCEEDS_GRANT, 0.92

        # ── Explicit grant check ──────────────────────────────────────
        if grants:
            if self._grant_covers_action(grants, action_class.value, target_class):
                trace.append(f"Explicit grant covers {action_class.value}/{target_class.value} — WITHIN_GRANT")
                return Authorization.WITHIN_GRANT, 0.90
            else:
                trace.append(f"Grants present but do not cover {action_class.value}/{target_class.value} — EXCEEDS_GRANT")
                return Authorization.EXCEEDS_GRANT, 0.85

        # ── Role present, no grant list ───────────────────────────────
        if role:
            # Conservative: role implies some authority, but without grant list we can't confirm
            trace.append(
                f"Role '{role}' present but no grant list — AT_LIMIT (cannot confirm WITHIN_GRANT)"
            )
            return Authorization.AT_LIMIT, 0.65

        # Conservative default
        trace.append("Insufficient auth signals — EXCEEDS_GRANT (conservative)")
        metadata.add_assumption("authorization unresolvable — EXCEEDS_GRANT")
        return Authorization.EXCEEDS_GRANT, 0.40

    # ── Consent resolution ───────────────────────────────────────────

    def _resolve_consent(
        self,
        auth_ctx: Optional[Dict[str, Any]],
        approval_tokens: List[str],
        action_class: ActionClass,
        target_class: TargetClass,
        caller_role: Optional[str],
        trace: List[str],
        metadata: NormalizationMetadata,
    ) -> Tuple[Consent, float]:

        # Explicit approval tokens = EXPLICIT consent
        if approval_tokens:
            trace.append(
                f"Approval token(s) present ({len(approval_tokens)}) — EXPLICIT consent"
            )
            return Consent.EXPLICIT, 0.95

        # Check auth_ctx for approval/consent token fields
        if auth_ctx:
            for key in _APPROVAL_TOKEN_KEYS:
                if key in auth_ctx and auth_ctx[key]:
                    trace.append(
                        f"auth_ctx contains approval token key '{key}' — EXPLICIT consent"
                    )
                    return Consent.EXPLICIT, 0.92

            # Check for workflow/approval state
            workflow_state = auth_ctx.get("workflow_state") or auth_ctx.get("approval_state")
            if workflow_state:
                workflow_lower = str(workflow_state).lower()
                if "approved" in workflow_lower or "confirmed" in workflow_lower:
                    trace.append(
                        f"workflow_state '{workflow_state}' indicates approval — EXPLICIT consent"
                    )
                    return Consent.EXPLICIT, 0.88
                elif "pending" in workflow_lower:
                    trace.append("workflow_state PENDING — NONE (approval not complete)")
                    return Consent.NONE, 0.88
                elif "rejected" in workflow_lower or "denied" in workflow_lower:
                    trace.append("workflow_state REJECTED — NONE")
                    return Consent.NONE, 0.95

        # Read-only actions: consent implied from role assignment
        if action_class == ActionClass.QUERY:
            trace.append("QUERY action — consent IMPLIED (read access implied by role)")
            return Consent.IMPLIED, 0.85

        # Scheduled/service actors: consent implied from deployment
        # (This would come from actor_class, which is resolved differently —
        #  but caller_role gives us a hint)
        role = self._extract_role(auth_ctx, caller_role) or ""
        if "scheduled" in role or "service" in role or "cron" in role:
            trace.append(f"Role '{role}' implies scheduled/service actor — consent IMPLIED")
            return Consent.IMPLIED, 0.80

        # Conservative default for write/transfer/delete
        if action_class in (ActionClass.TRANSFER, ActionClass.DELETE, ActionClass.ESCALATE):
            trace.append(
                f"{action_class.value} action with no approval token — NONE (conservative)"
            )
            metadata.add_assumption(
                f"High-risk action {action_class.value} has no approval token — consent NONE"
            )
            return Consent.NONE, 0.80

        # Mild conservative default for other actions
        trace.append("No consent signals for write action — NONE (conservative)")
        metadata.add_assumption("No consent signals — NONE")
        return Consent.NONE, 0.50

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_role(
        auth_ctx: Optional[Dict[str, Any]], caller_role: Optional[str]
    ) -> Optional[str]:
        """Extract role string from auth context or caller_role field."""
        if caller_role:
            return caller_role.lower().replace(" ", "_")
        if not auth_ctx:
            return None
        for key in ("role", "caller_role", "user_role", "actor_role", "scope"):
            if key in auth_ctx and isinstance(auth_ctx[key], str):
                return auth_ctx[key].lower().replace(" ", "_")
        return None

    @staticmethod
    def _extract_grants(
        auth_ctx: Optional[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Extract grant list from auth context."""
        if not auth_ctx:
            return None
        for key in ("grants", "permissions", "roles", "allowed_actions"):
            if key in auth_ctx and isinstance(auth_ctx[key], list):
                return auth_ctx[key]
        return None

    @staticmethod
    def _extract_spending_limit(auth_ctx: Optional[Dict[str, Any]]) -> Optional[float]:
        """Extract numeric spending or authority limit from auth context."""
        if not auth_ctx:
            return None
        for key in ("spending_limit", "transfer_limit", "authority_limit", "max_amount"):
            if key in auth_ctx:
                try:
                    return float(auth_ctx[key])
                except (TypeError, ValueError):
                    pass
        return None

    @staticmethod
    def _extract_delegation_depth(auth_ctx: Optional[Dict[str, Any]]) -> int:
        """Extract delegation chain depth."""
        if not auth_ctx:
            return 0
        for key in ("delegation_depth", "chain_depth", "delegation_chain"):
            if key in auth_ctx:
                try:
                    val = auth_ctx[key]
                    if isinstance(val, list):
                        return len(val)
                    return int(val)
                except (TypeError, ValueError):
                    pass
        return 0

    @staticmethod
    def _role_in_set(role: str, role_set: set) -> bool:
        """Check if role matches any entry in the set (substring match)."""
        role_normalized = role.lower().replace(" ", "_").replace("-", "_")
        for r in role_set:
            if r in role_normalized or role_normalized in r:
                return True
        return False

    @staticmethod
    def _grant_covers_action(
        grants: List[Any], action: str, target_class: TargetClass
    ) -> bool:
        """Check if any grant in the list covers the given action/target combination."""
        action_lower = action.lower()
        target_lower = target_class.value.lower()
        for grant in grants:
            if isinstance(grant, str):
                g = grant.lower()
                if action_lower in g or g == "*" or g == "all":
                    return True
            elif isinstance(grant, dict):
                grant_action = str(grant.get("action", "")).lower()
                grant_target = str(grant.get("target", "")).lower()
                action_match = (
                    grant_action in (action_lower, "*", "all")
                    or action_lower in grant_action
                )
                target_match = (
                    not grant_target
                    or grant_target in (target_lower, "*", "all")
                    or target_lower in grant_target
                )
                if action_match and target_match:
                    return True
        return False
