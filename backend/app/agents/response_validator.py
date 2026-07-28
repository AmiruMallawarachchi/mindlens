# backend/app/agents/response_validator.py
"""
Response Validator
==================
Hard guardrails against therapeutic hallucinations.
Runs AFTER agent generation, BEFORE response reaches user.
Blocks: diagnostic claims, medication advice, absolute certainty,
        self-harm encouragement, clinical guarantees.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from re import Pattern

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Forbidden pattern categories
# ---------------------------------------------------------------------------

# Diagnostic claims (MindLens is NOT a clinical service)
_RE_DIAGNOSTIC: Pattern = re.compile(
    r"\b(you have|you are suffering from|you are diagnosed with|"
    r"you meet the criteria for|this is|that is)\s+"
    r"(depression|anxiety disorder|bipolar|schizophrenia|ptsd|ocd|"
    r"adhd|autism|borderline personality|eating disorder|"
    r"clinical depression|major depressive disorder|generalized anxiety)",
    re.IGNORECASE,
)

# Medication advice (absolutely prohibited)
_RE_MEDICATION: Pattern = re.compile(
    r"\b(you should take|i recommend|try taking|start taking|"
    r"consider medication|ask your doctor for|prescription of|"
    r"dosage of|mg of|milligrams of|prozac|zoloft|lexapro|xanax|"
    r"valium|ativan|klonopin|adderall|ritalin|wellbutrin|"
    r"sertraline|fluoxetine|escitalopram|alprazolam)\b",
    re.IGNORECASE,
)

# Absolute certainty (undermines therapeutic alliance)
_RE_CERTAINTY: Pattern = re.compile(
    r"\b(definitely will|certainly will|absolutely|guaranteed|"
    r"you will feel better|this will fix|this will cure|"
    r"this always works|this is the only way|you must|you have to)\b",
    re.IGNORECASE,
)

# Self-harm encouragement (critical safety)
_RE_HARM_ENCOURAGEMENT: Pattern = re.compile(
    r"\b(you should end it|just kill yourself|nobody would miss you|"
    r"you're better off dead|hurt yourself|cut yourself|"
    r"jump off|overdose on|hang yourself)\b",
    re.IGNORECASE,
)

# Professional replacement claims (scope violation)
_RE_REPLACEMENT: Pattern = re.compile(
    r"\b(i am your therapist|i can replace your therapist|"
    r"you don't need a therapist|skip your therapy session|"
    r"cancel your appointment|i'm better than a human therapist)\b",
    re.IGNORECASE,
)

# Crisis minimization (dangerous)
_RE_MINIMIZATION: Pattern = re.compile(
    r"\b(it's not that bad|you're overreacting|just calm down|"
    r"other people have it worse|it's all in your head|"
    r"just think positive|just get over it)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationReport:
    """Immutable result of response validation."""

    passed: bool
    blocked_categories: list[str]
    severity: str  # "clean", "warning", "critical"
    original_length: int
    cleaned_text: str | None = None


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class ResponseValidator:
    """
    Stateless validator. Thread-safe. No external dependencies.
    Runs regex patterns against generated text. Returns report.
    """

    # Ordered by severity: critical patterns checked first
    PATTERNS: dict[str, Pattern] = {
        "harm_encouragement": _RE_HARM_ENCOURAGEMENT,
        "medication": _RE_MEDICATION,
        "diagnostic": _RE_DIAGNOSTIC,
        "replacement": _RE_REPLACEMENT,
        "minimization": _RE_MINIMIZATION,
        "certainty": _RE_CERTAINTY,
    }

    def validate(self, text: str) -> ValidationReport:
        """
        Check text against all forbidden patterns.
        Returns report with severity classification.
        """
        if not text or not isinstance(text, str):
            return ValidationReport(
                passed=False,
                blocked_categories=["empty_input"],
                severity="critical",
                original_length=0,
            )

        blocked: list[str] = []
        severity = "clean"

        for category, pattern in self.PATTERNS.items():
            if pattern.search(text):
                blocked.append(category)
                # Escalate severity
                if category in {"harm_encouragement", "medication"}:
                    severity = "critical"
                elif severity != "critical":
                    severity = "warning"

        passed = len(blocked) == 0

        if not passed:
            logger.warning(
                "Response validation FAILED: categories=%s, severity=%s",
                blocked,
                severity,
            )

        return ValidationReport(
            passed=passed,
            blocked_categories=blocked,
            severity=severity,
            original_length=len(text),
            cleaned_text=text if passed else None,
        )

    def validate_or_raise(self, text: str) -> str:
        """
        Validate and return text if clean. Raise if blocked.
        Used by response_assembler for hard stops.
        """
        report = self.validate(text)
        if not report.passed:
            raise ValueError(
                f"Response blocked: {report.blocked_categories} "
                f"(severity: {report.severity})"
            )
        return text

    def audit(self, text: str) -> dict[str, list[str]]:
        """
        Return all matches found without blocking.
        Useful for logging and BERTScore evaluation.
        """
        findings: dict[str, list[str]] = {}
        for category, pattern in self.PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                findings[category] = matches
        return findings


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------
_default_validator = ResponseValidator()


def validate(text: str) -> ValidationReport:
    """One-shot validation using default instance."""
    return _default_validator.validate(text)
