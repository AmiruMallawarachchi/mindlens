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
    # No country on file, so nobody's local numbers are asserted on their
    # behalf — the international rows are the only ones that are safe to show.
    assert "your local emergency number" in numbers
    assert not ({"1926", "119 / 110", "988"} & numbers)


@pytest.mark.asyncio
async def test_crisis_resources_follow_the_stored_country() -> None:
    graph = HostedGraphOrchestrator()
    with patch("app.agents.hosted_graph.get_groq_client"), patch(
        "app.agents.hosted_graph.get_hosted_retriever"
    ):
        result = await graph.run_full_pipeline(
            "I want to kill myself tonight",
            memory={"preferences": {"crisis_country": "GB"}},
        )

    rows = result["agent_outputs"][0]["metadata"]["resources"]
    assert rows[0] == {"name": "Samaritans (UK)", "number": "116 123"}
    # The international rows stay appended, so a wrong setting is never a
    # dead end.
    assert rows[-1]["name"] == "Befrienders Worldwide - emotional support"


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
async def test_retrieval_failure_is_blamed_on_retrieval_not_on_the_language_model() -> None:
    """`rag:`-prefixed degradations are the frontend's only signal that the
    reply itself was fine and only the lookup broke."""
    graph = HostedGraphOrchestrator()
    client = MagicMock()
    client.chat = AsyncMock(
        side_effect=[
            MagicMock(
                text='{"surface_emotion":"distress","distress_level":0.8,"route":"reflection","crisis_risk":false}'
            ),
            MagicMock(text="Let's slow this down together."),
        ]
    )
    retriever = MagicMock()
    retriever.retrieve = MagicMock(side_effect=RuntimeError("401 UNAUTHENTICATED"))
    with patch("app.agents.hosted_graph.get_groq_client", return_value=client), patch(
        "app.agents.hosted_graph.get_hosted_retriever", return_value=retriever
    ):
        result = await graph.run_full_pipeline(
            "I keep missing the dissertation deadline and it is getting worse"
        )

    assert "rag:pinecone" in result["degraded"]
    assert result["telemetry"]["rag"] == {"status": "failed", "chunks": 0}


@pytest.mark.asyncio
async def test_groq_stub_fallback_reaches_the_turns_degraded_list() -> None:
    """GroqClient records fallbacks into a per-run sink instead of the graph
    state, so the plumbing that carries them out of `ainvoke` is what stops a
    canned reply being presented as generated therapy."""
    from app.agents import groq_client as groq_client_module

    graph = HostedGraphOrchestrator()
    calls = {"n": 0}

    async def flaky_chat(**_kwargs):
        calls["n"] += 1
        groq_client_module._record_degradation("api_error")
        if calls["n"] == 1:
            return MagicMock(
                text='{"surface_emotion":"neutral","distress_level":0.2,"route":"empathy","crisis_risk":false}'
            )
        return MagicMock(text="I'm here with you.")

    client = MagicMock()
    client.chat = flaky_chat
    retriever = MagicMock()
    retriever.retrieve = MagicMock(return_value=["a passage"])
    with patch("app.agents.hosted_graph.get_groq_client", return_value=client), patch(
        "app.agents.hosted_graph.get_hosted_retriever", return_value=retriever
    ):
        result = await graph.run_full_pipeline("Work has been hard and I am tired")

    assert calls["n"] == 2
    assert "api_error" in result["degraded"]


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
    memory = {
        "people": {"Ravi": {"role": "best friend"}},
        "preferences": {
            "tone_preference": "direct",
            "personality": "introvert",
            "custom_instructions": "No breathing exercises.",
        },
    }
    with patch("app.agents.hosted_graph.get_groq_client", return_value=client), patch(
        "app.agents.hosted_graph.get_hosted_retriever"
    ) as retriever:
        retriever.return_value.retrieve.return_value = []
        result = await graph.run_full_pipeline(
            "I talked to Ravi today and I still feel anxious about work",
            memory=memory,
        )

    assert any("Ravi" in signal for signal in result["memory_recalled"])
    # Settings > General used to be stored but never reached the reply prompt.
    assert result["eos"]["tone_preference"] == "direct"
    specialist_prompt = client.chat.await_args_list[1].kwargs["user_prompt"]
    assert "direct" in specialist_prompt
    assert "No breathing exercises." in specialist_prompt
