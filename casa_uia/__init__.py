"""
CASA Universal Intake Adapter (UIA)
=====================================
Normalizes heterogeneous agent execution requests from any framework
into a Canonical Action Vector for deterministic CASA gate evaluation.

    from casa_uia import CasaAdapter

    adapter = CasaAdapter(gate_url="https://casa-gate.onrender.com")
    result = adapter.evaluate(
        framework="openai",
        tool_call=tool_call_object,
        authorization_context={"role": "capital_allocator", "spending_limit": 500000},
        domain="pe_fund",
    )

    if result.execution_blocked:
        raise RuntimeError(f"Refused. Trace: {result.gate_result.trace_id}")

© 2025-2026 Christopher T. Herndon / The Resonance Institute, LLC
USPTO Provisional Patent #63/987,813
"""

from .adapter import AdapterResult, CasaAdapter, GateResult
from .cnl.pipeline import ConstitutionalNormalizationLayer
from .models import (
    ActionClass,
    ActorClass,
    Authorization,
    CanonicalActionVector,
    Consent,
    IntermediateIntentObject,
    Magnitude,
    NormalizationMetadata,
    NormalizationResult,
    NormalizationStatus,
    Reversibility,
    Scope,
    TargetClass,
    Timing,
)
from .shims.langchain_shim import LangChainShim
from .shims.openai_shim import OpenAIToolCallShim

__version__ = "1.0.0"
__author__ = "Christopher T. Herndon / The Resonance Institute, LLC"
__patent__ = "USPTO Provisional #63/987,813"

__all__ = [
    "CasaAdapter",
    "AdapterResult",
    "GateResult",
    "ConstitutionalNormalizationLayer",
    "IntermediateIntentObject",
    "CanonicalActionVector",
    "NormalizationResult",
    "NormalizationMetadata",
    "NormalizationStatus",
    "OpenAIToolCallShim",
    "LangChainShim",
    "ActorClass",
    "ActionClass",
    "TargetClass",
    "Scope",
    "Magnitude",
    "Authorization",
    "Timing",
    "Consent",
    "Reversibility",
]
