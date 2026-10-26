"""Smoke-test imports for the live backend entrypoints."""

from __future__ import annotations


def test_import_core_backend_modules() -> None:
    import app.main  # noqa: F401
    import app.middleware.auth  # noqa: F401
