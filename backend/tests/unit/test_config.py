"""Production configuration guardrail tests."""

from __future__ import annotations

import pytest
from app.config import Settings
from pydantic import ValidationError


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "mongodb_url": "mongodb+srv://mindlens.example.invalid/app",
        "jwt_secret_key": "access-secret-with-production-entropy",
        "jwt_refresh_secret_key": "refresh-secret-with-production-entropy",
        "admin_jwt_secret": "admin-secret-with-production-entropy",
        "encryption_key": "fernet-key-supplied-by-deployment",
        "groq_api_key": "provider-key-supplied-by-deployment",
        "cors_origins": ["https://mindlens.example"],
        "use_openai_stubs": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_configuration_derives_cross_site_cookie_security() -> None:
    configured = _production_settings()

    assert configured.is_production is True
    assert configured.effective_cookie_secure is True
    assert configured.effective_cookie_samesite == "none"


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("jwt_secret_key", "dev-secret-key-change-in-production", "JWT_SECRET_KEY"),
        ("mongodb_url", "mongodb://localhost:27017", "MONGODB_URL"),
        ("encryption_key", "", "ENCRYPTION_KEY"),
    ],
)
def test_production_rejects_insecure_required_values(
    field: str, value: object, expected: str
) -> None:
    with pytest.raises(ValidationError, match=expected):
        _production_settings(**{field: value})


def test_production_rejects_stubbed_provider() -> None:
    with pytest.raises(ValidationError, match="USE_OPENAI_STUBS"):
        _production_settings(use_openai_stubs=True)


@pytest.mark.parametrize("origins", [[], ["*"]])
def test_production_rejects_implicit_cors(origins: list[str]) -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        _production_settings(cors_origins=origins)


def test_cors_origins_accept_json_environment_format() -> None:
    configured = Settings(
        _env_file=None,
        cors_origins='["https://one.example", "https://two.example"]',
    )

    assert configured.cors_origins == [
        "https://one.example",
        "https://two.example",
    ]
