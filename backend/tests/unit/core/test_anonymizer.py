# tests/unit/core/test_anonymizer.py
"""Unit tests for PII anonymizer."""

from __future__ import annotations


from app.core.anonymizer import Anonymizer, anonymize


class TestAnonymizer:
    """Validate regex-based PII stripping."""

    def test_email_stripped(self) -> None:
        text = "Contact me at john@example.com please"
        result = anonymize(text)
        assert "[EMAIL]" in result
        assert "john@example.com" not in result

    def test_phone_stripped(self) -> None:
        text = "Call me at +94 11 269 6666"
        result = anonymize(text)
        assert "[PHONE]" in result
        assert "+94 11 269 6666" not in result

    def test_nic_stripped(self) -> None:
        text = "My NIC is 123456789V"
        result = anonymize(text)
        assert "[NIC]" in result

    def test_url_stripped(self) -> None:
        text = "Visit https://example.com/page"
        result = anonymize(text)
        assert "[URL]" in result

    def test_multiple_pii_in_one_text(self) -> None:
        text = "Email: alice@test.com, Phone: 0771234567, NIC: 987654321X"
        result = anonymize(text)
        assert "[EMAIL]" in result
        assert "[PHONE]" in result
        assert "[NIC]" in result

    def test_no_pii_unchanged(self) -> None:
        text = "I feel anxious about my exam tomorrow"
        result = anonymize(text)
        assert result == text

    def test_empty_string(self) -> None:
        assert anonymize("") == ""

    def test_audit_returns_findings(self) -> None:
        """audit() reports what would be stripped without stripping."""
        a = Anonymizer(use_ner=False)
        text = "Email: bob@site.com"
        findings = a.audit(text)
        assert "email" in findings
        assert len(findings["email"]) == 1

    def test_audit_empty_when_clean(self) -> None:
        a = Anonymizer(use_ner=False)
        findings = a.audit("Just a normal sentence")
        assert findings == {}