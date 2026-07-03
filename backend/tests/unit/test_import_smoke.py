"""Backend import smoke tests.

These tests ensure the backend package can be imported cleanly enough for CI to
catch missing dependency or broken module wiring issues before deeper tests run.
"""

from __future__ import annotations


def test_import_core_backend_modules() -> None:
    """Import the main backend entrypoints and model loader."""
    import app.main  # noqa: F401
    import app.agents.orchestrator  # noqa: F401
    import app.middleware.auth  # noqa: F401
    import app.models.loader  # noqa: F401
    import app.rag.retriever  # noqa: F401
