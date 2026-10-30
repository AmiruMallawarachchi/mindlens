"""Integration coverage for the shared text anonymizer."""

from app.core.anonymizer import anonymize


def test_anonymizer_removes_email() -> None:
    clean = anonymize("Contact me at john@doe.com")
    assert clean == "Contact me at [EMAIL]"
