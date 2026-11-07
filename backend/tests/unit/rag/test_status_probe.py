"""The admin status probe asks Pinecone instead of reading the config back."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.rag import hosted_retriever as retriever_module
from app.rag.hosted_retriever import probe_rag, rag_status


class RejectionError(RuntimeError):
    """Stands in for the SDK's exceptions, which carry the HTTP status."""

    def __init__(self, status: int) -> None:
        super().__init__(f"{status} UNAUTHENTICATED")
        self.status = status


def _pinecone(**overrides: object) -> MagicMock:
    client = MagicMock()
    client.describe_index.return_value = MagicMock(dimension=1024)
    for name, value in overrides.items():
        setattr(client.describe_index, name, value)
    return client


class TestProbeRag:
    def test_missing_key_is_not_reported_as_a_connection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(retriever_module.settings, "pinecone_api_key", "")
        monkeypatch.setattr(retriever_module.settings, "pinecone_index_name", "mindlens")
        assert probe_rag() == {"provider": "pinecone", "status": "not_configured"}

    @pytest.mark.parametrize("status", [401, 403])
    def test_rejected_key_says_unauthorized(
        self, monkeypatch: pytest.MonkeyPatch, status: int
    ) -> None:
        monkeypatch.setattr(retriever_module.settings, "pinecone_api_key", "pcsk_bogus")
        monkeypatch.setattr(retriever_module.settings, "pinecone_index_name", "mindlens")
        client = _pinecone(side_effect=RejectionError(status))
        with patch("pinecone.Pinecone", return_value=client):
            assert probe_rag()["status"] == "unauthorized"

    def test_missing_index_is_named(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(retriever_module.settings, "pinecone_api_key", "pcsk_ok")
        monkeypatch.setattr(retriever_module.settings, "pinecone_index_name", "gone")
        client = _pinecone(side_effect=RejectionError(404))
        with patch("pinecone.Pinecone", return_value=client):
            result = probe_rag()
        assert result["status"] == "index_not_found"
        assert "gone" in result["detail"]

    def test_working_index_reports_reachable_with_its_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(retriever_module.settings, "pinecone_api_key", "pcsk_ok")
        monkeypatch.setattr(retriever_module.settings, "pinecone_index_name", "mindlens")
        client = _pinecone()
        with patch("pinecone.Pinecone", return_value=client):
            result = probe_rag()
        assert result == {
            "provider": "pinecone",
            "status": "reachable",
            "index": "mindlens",
            "dimension": 1024,
        }
        client.describe_index.assert_called_once_with("mindlens")

    def test_a_failure_without_a_status_is_unreachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(retriever_module.settings, "pinecone_api_key", "pcsk_ok")
        monkeypatch.setattr(retriever_module.settings, "pinecone_index_name", "mindlens")
        client = _pinecone(side_effect=OSError("dns down"))
        with patch("pinecone.Pinecone", return_value=client):
            result = probe_rag()
        assert result["status"] == "unreachable"
        assert "dns down" in result["detail"]


class TestRagStatus:
    async def test_a_hanging_controller_does_not_hang_the_request(self) -> None:
        def never(*_: object) -> dict[str, str]:
            import time

            time.sleep(retriever_module.PROBE_TIMEOUT_SECONDS + 1)
            return {"provider": "pinecone", "status": "reachable"}

        with patch.object(retriever_module, "probe_rag", never):
            result = await rag_status()

        assert result["status"] == "unreachable"
        assert str(retriever_module.PROBE_TIMEOUT_SECONDS) in result["detail"]

    async def test_passes_the_probe_result_through(self) -> None:
        probe = {"provider": "pinecone", "status": "reachable", "dimension": 1024}
        with patch.object(retriever_module, "probe_rag", return_value=probe):
            assert await rag_status() == probe
