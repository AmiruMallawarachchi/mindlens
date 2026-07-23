"""Readiness response guardrails."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app import main as main_module
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_readiness_does_not_claim_lazy_models_are_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module.settings, "deployment_mode", "render_free_demo")
    monkeypatch.setattr(main_module.settings, "preload_models", False)
    monkeypatch.setattr(main_module.settings, "preload_rag", False)
    monkeypatch.setattr(main_module.settings, "rag_retrieval_mode", "auto")
    monkeypatch.setattr(main_module.settings, "chromadb_persist_dir", "/tmp/mindlens/chroma")

    client = MagicMock()
    client.admin.command = AsyncMock(return_value={"ok": 1})
    model_health: dict[str, dict[str, Any]] = {
        "crisis": {
            "status": "error",
            "model_id": "AmiruMallawarachchi/mindlens-crisis",
            "backend": "onnx",
        }
    }

    with (
        patch.object(main_module, "get_db_client", return_value=client),
        patch.object(main_module.model_manager, "health_status", return_value=model_health),
        patch.object(main_module.model_manager, "resident_model_count", return_value=0),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=main_module.create_app()),
            base_url="http://test",
        ) as http:
            response = await http.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["models"]["crisis"]["status"] == "error"
    assert payload["models"]["crisis"]["status"] != "ready"
    assert payload["rag"]["persist_dir"] == "/tmp/mindlens/chroma"
