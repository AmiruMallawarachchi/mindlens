"""Contract tests for the hosted V2 LangGraph runtime."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.hosted_graph import HostedGraphOrchestrator


@pytest.mark.asyncio
async def test_regex_crisis_exits_before_groq_and_retrieval() -> None:
    graph = HostedGraphOrchestrator()
    with patch("app.agents.hosted_graph.get_groq_client") as groq, patch(
        "app.agents.hosted_graph.get_hosted_retriever"
    ) as retriever:
        result = await graph.run_full_pipeline("I want to kill myself tonight")

    groq.assert_not_called()
    retriever.assert_not_called()
    assert result["crisis_flag"] is True
    assert result["agents"] == ["crisis"]
    assert result["telemetry"]["graph"]["nodes"] == ["safety_gate", "finalize"]
    numbers = {row["number"] for row in result["agent_outputs"][0]["metadata"]["resources"]}
    assert {"1926", "119 / 110"} <= numbers


@pytest.mark.asyncio
async def test_safe_turn_routes_to_one_specialist_and_optional_review() -> None:
    graph = HostedGraphOrchestrator()
    client = MagicMock()
    client.chat = AsyncMock(
        side_effect=[
            MagicMock(
                text='{"surface_emotion":"anxiety","surface_confidence":0.7,"core_emotion":"anxiety","distress_level":0.4,"route":"empathy","crisis_risk":false,"review_required":false}',
            ),
            MagicMock(text="That sounds like a lot to hold. What part feels most pressing right now?"),
        ]
    )
    pinecone = MagicMock()
    pinecone.retrieve.return_value = ["A short grounding passage."]
    with patch("app.agents.hosted_graph.get_groq_client", return_value=client), patch(
        "app.agents.hosted_graph.get_hosted_retriever", return_value=pinecone
    ):
        result = await graph.run_full_pipeline("I feel anxious about work tomorrow")

    assert client.chat.await_count == 2
    assert result["crisis_flag"] is False
    assert len(result["agents"]) == 1
    assert result["telemetry"]["graph"]["route"] == "empathy"
    assert result["assembled_text"].startswith("That sounds")


@pytest.mark.asyncio
async def test_assessment_crisis_stops_before_specialist() -> None:
    graph = HostedGraphOrchestrator()
    client = MagicMock()
    client.chat = AsyncMock(
        return_value=MagicMock(
            text='{"surface_emotion":"distress","core_emotion":"hopelessness","distress_level":0.95,"route":"empathy","crisis_risk":true,"crisis_confidence":0.91}'
        )
    )
    with patch("app.agents.hosted_graph.get_groq_client", return_value=client):
        result = await graph.run_full_pipeline("I cannot see a way through this")

    assert client.chat.await_count == 1
    assert result["crisis_flag"] is True
    assert result["agents"] == ["crisis"]
    assert "specialist" not in result["telemetry"]["graph"]["nodes"]


@pytest.mark.asyncio
async def test_malformed_assessment_degrades_without_inventing_emotion() -> None:
    graph = HostedGraphOrchestrator()
    client = MagicMock()
    client.chat = AsyncMock(
        side_effect=[MagicMock(text="not json"), MagicMock(text="I hear you. What feels hardest right now?")]
    )
    with patch("app.agents.hosted_graph.get_groq_client", return_value=client):
        result = await graph.run_full_pipeline("I have had a difficult day at work")

    assert client.chat.await_count == 2
    assert "assessment" in result["degraded"]
    assert result["eos"]["surface_emotion"] == "neutral"


@pytest.mark.asyncio
async def test_reviewer_is_the_third_and_final_allowed_groq_call() -> None:
    graph = HostedGraphOrchestrator()
    client = MagicMock()
    client.chat = AsyncMock(
        side_effect=[
            MagicMock(text='{"surface_emotion":"distress","distress_level":0.8,"route":"reflection","review_required":true}'),
            MagicMock(text="Let's slow this down together and find one manageable next step."),
            MagicMock(text='{"approved":true,"replacement":""}'),
        ]
    )
    with patch("app.agents.hosted_graph.get_groq_client", return_value=client):
        result = await graph.run_full_pipeline("Everything feels overwhelming and impossible today")

    assert client.chat.await_count == 3
    assert result["telemetry"]["llm"]["count"] == 3
    assert "review" in result["telemetry"]["graph"]["nodes"]


@pytest.mark.asyncio
async def test_memory_recall_surfaces_a_person_the_user_mentioned() -> None:
    """user_memory was readable and editable but no V2 turn ever read it
    back, so the thinking panel's memory line was always empty. The graph
    now runs core/memory_recall.recall_for_turn, which surfaces only what is
    relevant to this message."""
    graph = HostedGraphOrchestrator()
    client = MagicMock()
    client.chat = AsyncMock(
        side_effect=[
            MagicMock(
                text='{"surface_emotion":"anxiety","distress_level":0.4,"route":"empathy","crisis_risk":false,"review_required":false}'
            ),
            MagicMock(text="It sounds like talking to Ravi helped a little."),
        ]
    )
    memory = {"people": {"Ravi": {"role": "best friend"}}, "preferences": {}}
    with patch("app.agents.hosted_graph.get_groq_client", return_value=client), patch(
        "app.agents.hosted_graph.get_hosted_retriever"
    ) as retriever:
        retriever.return_value.retrieve.return_value = []
        result = await graph.run_full_pipeline(
            "I talked to Ravi today and I still feel anxious about work",
            memory=memory,
        )

    assert any("Ravi" in signal for signal in result["memory_recalled"])
