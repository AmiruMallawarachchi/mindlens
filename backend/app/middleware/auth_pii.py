"""PII anonymization helpers for model-bound request data."""

from __future__ import annotations

import re
from typing import Any

from app.config import settings

# ---------------------------------------------------------------------------
# PII Anonymizer (for request body before model calls)
# ---------------------------------------------------------------------------

# Simple regex-based PII patterns (matches names, emails, phones, addresses)
_PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL]'),
    (re.compile(r'\b(?:\+94\s?)?(?:0\s?)?(?:7[0-9]\s?\d{8}|\d{10})\b'), '[PHONE]'),
    (re.compile(r'\b\d{1,4}\s+[A-Za-z]+\s+(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr)\b', re.IGNORECASE), '[ADDRESS]'),
]


def anonymize_text(text: str) -> str:
    """
    Strip PII from text before sending to ML models.
    Non-destructive — returns redacted version for model input.
    """
    if not settings.ANONYMIZER_ENABLED:
        return text
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def anonymize_request_body(body: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively anonymize a request body dict/list.
    Targets 'text', 'message', 'content' fields.
    """
    if not settings.ANONYMIZER_ENABLED:
        return body

    def _anonymize(obj: Any) -> Any:
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k in ("text", "message", "content") and isinstance(v, str):
                    result[k] = anonymize_text(v)
                else:
                    result[k] = _anonymize(v)
            return result
        elif isinstance(obj, list):
            return [_anonymize(i) for i in obj]
        elif isinstance(obj, str):
            return anonymize_text(obj)
        return obj

    return _anonymize(body)


