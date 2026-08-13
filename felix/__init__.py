"""Felix — extract Salesforce constraints that will break AI agents."""

from felix.diagnose import (
    Diagnosis,
    EscalationPayload,
    RetryDecision,
    build_escalation,
    diagnose_error,
    retry_guard,
)
from felix.models import (
    ApexConstraint,
    ErrorSignature,
    EvalCase,
    FieldConstraint,
    ScanError,
    ScanResult,
    ValidationRuleConstraint,
)
from felix.scan import scan_org

__version__ = "0.1.0"

__all__ = [
    "ApexConstraint",
    "Diagnosis",
    "ErrorSignature",
    "EscalationPayload",
    "EvalCase",
    "FieldConstraint",
    "RetryDecision",
    "ScanError",
    "ScanResult",
    "ValidationRuleConstraint",
    "__version__",
    "build_escalation",
    "diagnose_error",
    "retry_guard",
    "scan_org",
]
