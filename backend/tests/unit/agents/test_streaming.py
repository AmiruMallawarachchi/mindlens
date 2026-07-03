"""Tests for MindLens Streaming Module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.agents.base_agent import AgentOutput
from app.agents.streaming import (
    StreamingResponse,
    stream_agent_output,
    stream_pipeline_result,
)
from app.core.connection_manager import ConnectionManager
from app.core.emotional_os import EmotionalOperatingState


class TestStreamingResponseChunking:
    """Tests for text chunking utility."""

    def test_chunk_text_short(self) -> None:
        chunks = StreamingResponse._chunk_text("Hello", 8)
        assert chunks == ["Hello"]

    def test_chunk_text_long(self) -> None:
        text = "This is a longer sentence that needs chunking."
        chunks = StreamingResponse._chunk_text(text, 10)
        assert len(chunks) > 1
        # All chunks except last should be <= 10
        for chunk in chunks[:-1]:
            assert len(chunk) <= 10
        # Reconstructed should be original
        reconstructed = ""
        for chunk in chunks:
            reconstructed += chunk
        assert reconstructed == text

    def test_chunk_text_respects_word_boundaries(self) -> None:
        text = "Hello world this is a test"
        chunks = StreamingResponse._chunk_text(text, 12)
        # Should break at spaces when possible
        for chunk in chunks[:-1]:
            # Last character should be end of a word (or space)
            assert chunk[-1] in " " or chunk[-1] == text[len(chunk) - 1]

    def test_chunk_text_no_spaces(self) -> None:
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        chunks = StreamingResponse._chunk_text(text, 5)
        assert len(chunks) == 6  # 5+5+5+5+5+1
        assert chunks[0] == "ABCDE"


class TestStreamingResponse:
    """Tests for StreamingResponse class."""

    @pytest.fixture
    def mock_manager(self) -> MagicMock:
        manager = MagicMock(spec=ConnectionManager)
        manager.send_thinking_update = AsyncMock(return_value=True)
        manager.send_chunk = AsyncMock(return_value=True)
        manager.send_response = AsyncMock(return_value=True)
        manager.send_crisis_response = AsyncMock(return_value=True)
        manager.send_to_user = AsyncMock(return_value=True)
        return manager

    @pytest.mark.asyncio
    async def test_begin_thinking(self, mock_manager: MagicMock) -> None:
        streamer = StreamingResponse("user_123", "sess_abc", mock_manager)
        eos = EmotionalOperatingState(surface_emotion="anxiety")

        await streamer.begin_thinking(
            agents_active=["empathy_agent", "mindfulness_agent"],
            eos=eos,
            memory_recalled=["exam", "Ravi"],
        )

        mock_manager.send_thinking_update.assert_awaited_once()
        args = mock_manager.send_thinking_update.call_args[1]
        assert args["user_id"] == "user_123"
        assert args["agents_active"] == ["empathy_agent", "mindfulness_agent"]
        assert args["memory_recalled"] == ["exam", "Ravi"]

    @pytest.mark.asyncio
    async def test_stream_text(self, mock_manager: MagicMock) -> None:
        streamer = StreamingResponse("user_123", "sess_abc", mock_manager)
        text = "Hello world"

        await streamer.stream_text(text, chunk_size=5, delay_ms=0)

        # Should have sent multiple chunks
        assert mock_manager.send_chunk.call_count >= 2
        first_call = mock_manager.send_chunk.call_args_list[0][1]
        assert first_call["user_id"] == "user_123"
        assert first_call["chunk_index"] == 0

    @pytest.mark.asyncio
    async def test_end_stream_normal(self, mock_manager: MagicMock) -> None:
        streamer = StreamingResponse("user_123", "sess_abc", mock_manager)
        eos = EmotionalOperatingState(surface_emotion="joy")

        await streamer.end_stream(
            assembled_text="Everything is okay.",
            agents_used=["empathy_agent"],
            eos_snapshot=eos,
        )

        mock_manager.send_response.assert_awaited_once()
        args = mock_manager.send_response.call_args[1]
        assert args["user_id"] == "user_123"
        assert args["text"] == "Everything is okay."
        assert args["crisis_flag"] is False

    @pytest.mark.asyncio
    async def test_end_stream_crisis(self, mock_manager: MagicMock) -> None:
        streamer = StreamingResponse("user_123", "sess_abc", mock_manager)
        eos = EmotionalOperatingState(surface_emotion="desperate")

        await streamer.end_stream(
            assembled_text="Please call for help.",
            agents_used=["crisis_agent"],
            eos_snapshot=eos,
            crisis_flag=True,
            resources=[{"name": "NIMH", "number": "1926"}],
        )

        mock_manager.send_crisis_response.assert_awaited_once()
        args = mock_manager.send_crisis_response.call_args[1]
        assert args["user_id"] == "user_123"
        assert args["text"] == "Please call for help."
        assert args["resources"] == [{"name": "NIMH", "number": "1926"}]

    @pytest.mark.asyncio
    async def test_stream_text_empty(self, mock_manager: MagicMock) -> None:
        streamer = StreamingResponse("user_123", "sess_abc", mock_manager)
        await streamer.stream_text("", chunk_size=8)
        mock_manager.send_chunk.assert_not_awaited()


class TestStreamPipelineResult:
    """Tests for the high-level stream_pipeline_result function."""

    @pytest.fixture
    def mock_manager(self) -> MagicMock:
        manager = MagicMock(spec=ConnectionManager)
        manager.send_thinking_update = AsyncMock(return_value=True)
        manager.send_chunk = AsyncMock(return_value=True)
        manager.send_response = AsyncMock(return_value=True)
        manager.send_crisis_response = AsyncMock(return_value=True)
        return manager

    @pytest.mark.asyncio
    async def test_stream_pipeline_normal(self, mock_manager: MagicMock) -> None:
        pipeline_result = {
            "eos": {"surface_emotion": "anxiety", "distress_level": 0.5, "modality": "CBT"},
            "agents": ["empathy_agent", "mindfulness_agent"],
            "crisis_flag": False,
            "assembled_text": "I hear you. Let's take a breath together.",
            "agent_outputs": [],
        }

        await stream_pipeline_result(
            "user_123", "sess_abc", pipeline_result, mock_manager, enable_streaming=True
        )

        mock_manager.send_thinking_update.assert_awaited_once()
        mock_manager.send_response.assert_awaited_once()
        # Should have sent chunks (text is > 40 chars)
        assert mock_manager.send_chunk.call_count > 0

    @pytest.mark.asyncio
    async def test_stream_pipeline_crisis(self, mock_manager: MagicMock) -> None:
        pipeline_result = {
            "eos": {"surface_emotion": "desperate", "distress_level": 0.95, "modality": "DBT"},
            "agents": ["crisis_agent"],
            "crisis_flag": True,
            "assembled_text": "Please contact NIMH at 1926.",
            "agent_outputs": [
                {"agent": "crisis", "text": "Please contact NIMH at 1926.", "metadata": {
                    "resources": [{"name": "NIMH", "number": "1926"}]
                }}
            ],
        }

        await stream_pipeline_result(
            "user_123", "sess_abc", pipeline_result, mock_manager, enable_streaming=True
        )

        mock_manager.send_crisis_response.assert_awaited_once()
        args = mock_manager.send_crisis_response.call_args[1]
        assert args["text"] == "Please contact NIMH at 1926."
        assert args["resources"] == [{"name": "NIMH", "number": "1926"}]

    @pytest.mark.asyncio
    async def test_stream_pipeline_short_text(self, mock_manager: MagicMock) -> None:
        pipeline_result = {
            "eos": {"surface_emotion": "joy", "distress_level": 0.1, "modality": "CBT"},
            "agents": ["empathy_agent"],
            "crisis_flag": False,
            "assembled_text": "Hi.",
            "agent_outputs": [],
        }

        await stream_pipeline_result(
            "user_123", "sess_abc", pipeline_result, mock_manager, enable_streaming=True
        )

        # Short text should not stream chunks, just send response directly
        mock_manager.send_chunk.assert_not_awaited()
        mock_manager.send_response.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stream_pipeline_no_streaming(self, mock_manager: MagicMock) -> None:
        pipeline_result = {
            "eos": {"surface_emotion": "anxiety", "distress_level": 0.5, "modality": "CBT"},
            "agents": ["empathy_agent"],
            "crisis_flag": False,
            "assembled_text": "This is a longer response that would normally stream but we disabled it.",
            "agent_outputs": [],
        }

        await stream_pipeline_result(
            "user_123", "sess_abc", pipeline_result, mock_manager, enable_streaming=False
        )

        mock_manager.send_chunk.assert_not_awaited()
        mock_manager.send_response.assert_awaited_once()


class TestStreamAgentOutput:
    """Tests for stream_agent_output."""

    @pytest.fixture
    def mock_manager(self) -> MagicMock:
        manager = MagicMock(spec=ConnectionManager)
        manager.send_thinking_update = AsyncMock(return_value=True)
        manager.send_chunk = AsyncMock(return_value=True)
        manager.send_response = AsyncMock(return_value=True)
        return manager

    @pytest.mark.asyncio
    async def test_stream_agent_output(self, mock_manager: MagicMock) -> None:
        output = AgentOutput(
            agent_name="music_agent",
            text="Here's a calming playlist for you.",
            metadata={"mode": "B"},
        )
        eos = EmotionalOperatingState(surface_emotion="anxiety")

        await stream_agent_output("user_123", "sess_abc", output, eos, mock_manager)

        mock_manager.send_thinking_update.assert_awaited_once()
        mock_manager.send_response.assert_awaited_once()
        args = mock_manager.send_response.call_args[1]
        assert args["text"] == "Here's a calming playlist for you."
