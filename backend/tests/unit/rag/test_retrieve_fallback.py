"""Retrieval falls through to the vector path when integrated search comes
back empty, and the path it falls through to names the namespace."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.rag import hosted_retriever as retriever_module
from app.rag.hosted_retriever import HostedRetriever

TEXT = "I can't stop thinking about work at 2am"


def _retriever(
    monkeypatch: pytest.MonkeyPatch,
    search: object = None,
    matches: object = None,
) -> tuple[HostedRetriever, MagicMock]:
    monkeypatch.setattr(retriever_module.settings, "pinecone_api_key", "pcsk_ok")
    monkeypatch.setattr(retriever_module.settings, "pinecone_index_name", "mindlens")

    client = MagicMock()
    index = client.Index.return_value
    index.search.return_value = search
    index.query.return_value = {"matches": matches if matches is not None else []}
    client.inference.embed.return_value = [MagicMock(values=[0.0] * 1024)]

    with patch("pinecone.Pinecone", return_value=client):
        return HostedRetriever(), index


def _hit(text: object) -> dict:
    """One integrated hit; `None` text stands for a hit with no text field."""
    fields = {} if text is None else {"text": text}
    return {"score": 0.9, "fields": fields}


def _integrated(*texts: object) -> dict:
    return {"result": {"hits": [_hit(text) for text in texts]}}


def _records(*texts: str) -> list[dict]:
    return [{"score": 0.3, "metadata": {"text": t}} for t in texts]


class TestIntegratedFirst:
    def test_hits_from_integrated_search_are_used_as_is(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        retriever, index = _retriever(
            monkeypatch, search=_integrated("passage one", "passage two")
        )

        assert retriever.retrieve(TEXT) == ["passage one", "passage two"]
        index.query.assert_not_called()

    def test_a_hit_without_text_is_dropped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        retriever, _ = _retriever(monkeypatch, search=_integrated("passage one", None))

        assert retriever.retrieve(TEXT) == ["passage one"]


class TestFallsThroughOnEmpty:
    """The bug this guards: this index answers `hits: []` to every integrated
    search, so treating only exceptions as "try the other path" meant nothing
    was ever retrieved while the probe reported the index as reachable."""

    def test_empty_integrated_answer_queries_by_vector(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        retriever, index = _retriever(
            monkeypatch,
            search=_integrated(),
            matches=_records("sleep restriction passage"),
        )

        assert retriever.retrieve(TEXT) == ["sleep restriction passage"]
        assert index.query.call_args.kwargs["namespace"] == retriever_module.NAMESPACE

    def test_raising_integrated_search_also_falls_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        retriever, index = _retriever(monkeypatch, matches=_records("a passage"))
        index.search.side_effect = RuntimeError("400 not an integrated index")

        assert retriever.retrieve(TEXT) == ["a passage"]

    def test_the_default_namespace_is_never_queried(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        retriever, index = _retriever(monkeypatch, search=_integrated(), matches=[])

        retriever.retrieve(TEXT)

        assert index.query.call_args.kwargs["namespace"] == "therapy"

    def test_both_paths_empty_is_an_empty_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        retriever, _ = _retriever(monkeypatch, search=_integrated(), matches=[])

        assert retriever.retrieve(TEXT) == []

    def test_metadata_without_text_is_not_retrieved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        retriever, _ = _retriever(
            monkeypatch, search=_integrated(), matches=[{"score": 0.4, "metadata": {}}]
        )

        assert retriever.retrieve(TEXT) == []
