# backend/app/core/anonymizer.py
"""
PII Anonymizer
==============
Strips personally identifiable information BEFORE any model sees the text.
Zero-trust: assume all downstream services are untrusted.
Implements regex-first + optional NER fallback.
"""

from __future__ import annotations

import re
from typing import Pattern

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns (compiled once at import)
# ---------------------------------------------------------------------------

# Email addresses
_RE_EMAIL: Pattern = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Phone numbers (international formats, Sri Lankan, US, UK)
_RE_PHONE: Pattern = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}",
    re.IGNORECASE,
)

# National ID numbers (Sri Lankan NIC pattern: 9 digits + V/X or 12 digits)
_RE_NIC_LK: Pattern = re.compile(r"\b\d{9}[VXvx]|\b\d{12}\b")

# Passport numbers (generic alphanumeric)
_RE_PASSPORT: Pattern = re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")

# Credit card numbers (13-19 digits, with or without spaces/dashes)
_RE_CC: Pattern = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

# Bank account numbers (8-20 digits)
_RE_BANK: Pattern = re.compile(r"\b\d{8,20}\b")

# IP addresses
_RE_IP: Pattern = re.compile(
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b|\b[0-9a-fA-F:]{2,45}\b"
)

# URLs
_RE_URL: Pattern = re.compile(
    r"https?://[^\s]+|www\.[^\s]+",
    re.IGNORECASE,
)

# Common name indicators (Mr., Mrs., Dr., etc.) — weak signal, used with NER
_RE_NAME_PREFIX: Pattern = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof|Rev|Hon)\.?\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?\b",
    re.IGNORECASE,
)

# Physical addresses (simple street pattern)
_RE_ADDRESS: Pattern = re.compile(
    r"\b\d+\s+(?:[A-Za-z]+\s+){1,4}(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|court|ct|place|pl|way|boulevard|blvd)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Replacement tokens
# ---------------------------------------------------------------------------
_REPLACEMENTS: dict[str, str] = {
    "email": "[EMAIL]",
    "phone": "[PHONE]",
    "nic": "[NIC]",
    "passport": "[PASSPORT]",
    "cc": "[CREDIT_CARD]",
    "bank": "[BANK_ACCOUNT]",
    "ip": "[IP_ADDRESS]",
    "url": "[URL]",
    "name": "[NAME]",
    "address": "[ADDRESS]",
}


class Anonymizer:
    """
    Stateless PII stripper. Thread-safe. No external dependencies by default.
    Optional spaCy NER can be enabled for higher recall at the cost of latency.
    """

    def __init__(self, use_ner: bool = False) -> None:
        self.use_ner = use_ner
        self._ner = None
        if use_ner:
            # Lazy import so spaCy is optional
            try:
                import spacy  # type: ignore[import-untyped]
                self._ner = spacy.load("en_core_web_sm", disable=["parser", "tagger"])
                logger.info("spaCy NER loaded for anonymization.")
            except Exception as exc:
                logger.warning(f"spaCy NER unavailable: {exc}. Falling back to regex only.")

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def anonymize(self, text: str) -> str:
        """
        Strip all known PII patterns from text.
        Runs regex layers first (fast), then optional NER (slow but thorough).
        Returns scrubbed text ready for model inference.
        """
        if not text or not isinstance(text, str):
            return ""

        scrubbed = text

        # Layer 1: deterministic regex (fast, <1ms)
        scrubbed = self._regex_scrub(scrubbed)

        # Layer 2: NER fallback (only if enabled and available)
        if self.use_ner and self._ner is not None:
            scrubbed = self._ner_scrub(scrubbed)

        return scrubbed

    def audit(self, text: str) -> dict[str, list[str]]:
        """
        Return what WOULD be stripped without actually stripping.
        Useful for consent logs and GDPR Article 15 data exports.
        """
        findings: dict[str, list[str]] = {
            "email": _RE_EMAIL.findall(text),
            "phone": _RE_PHONE.findall(text),
            "nic": _RE_NIC_LK.findall(text),
            "passport": _RE_PASSPORT.findall(text),
            "cc": _RE_CC.findall(text),
            "bank": _RE_BANK.findall(text),
            "ip": _RE_IP.findall(text),
            "url": _RE_URL.findall(text),
            "name": _RE_NAME_PREFIX.findall(text),
            "address": _RE_ADDRESS.findall(text),
        }
        # Remove empty lists
        return {k: v for k, v in findings.items() if v}

    # -----------------------------------------------------------------------
    # Internal scrubbers
    # -----------------------------------------------------------------------

    @staticmethod
    def _regex_scrub(text: str) -> str:
        """Apply all compiled regexes in sequence."""
        text = _RE_EMAIL.sub(_REPLACEMENTS["email"], text)
        text = _RE_PHONE.sub(_REPLACEMENTS["phone"], text)
        text = _RE_NIC_LK.sub(_REPLACEMENTS["nic"], text)
        text = _RE_PASSPORT.sub(_REPLACEMENTS["passport"], text)
        text = _RE_CC.sub(_REPLACEMENTS["cc"], text)
        text = _RE_BANK.sub(_REPLACEMENTS["bank"], text)
        text = _RE_IP.sub(_REPLACEMENTS["ip"], text)
        text = _RE_URL.sub(_REPLACEMENTS["url"], text)
        text = _RE_NAME_PREFIX.sub(_REPLACEMENTS["name"], text)
        text = _RE_ADDRESS.sub(_REPLACEMENTS["address"], text)
        return text

    def _ner_scrub(self, text: str) -> str:
        """spaCy NER-based replacement for names, organizations, locations."""
        if self._ner is None:
            return text

        doc = self._ner(text)
        # Work backwards so offsets stay valid
        replacements = []
        for ent in doc.ents:
            if ent.label_ in {"PERSON", "ORG", "GPE", "LOC", "NORP"}:
                replacements.append((ent.start_char, ent.end_char, f"[{ent.label_}]"))

        # Apply in reverse order to preserve indices
        out = text
        for start, end, token in sorted(replacements, key=lambda x: x[0], reverse=True):
            out = out[:start] + token + out[end:]
        return out


# ---------------------------------------------------------------------------
# Module-level convenience function (most common usage)
# ---------------------------------------------------------------------------
_default_anonymizer = Anonymizer(use_ner=False)


def anonymize(text: str) -> str:
    """One-shot anonymize using default regex-only instance."""
    return _default_anonymizer.anonymize(text)