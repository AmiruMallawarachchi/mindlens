"""Unit tests for proactive check-in scheduling and delivery."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.checkins import (
    CHECKIN_FALLBACK_TEXT,
    generate_checkin_text,
    next_checkin_at,
    schedule_checkin,
    send_pending_checkin,
)

_NOW = datetime.datetime(2026, 1, 1, 10, 30, tzinfo=datetime.UTC)


def _groq(text: str | None = None, error: Exception | None = None) -> MagicMock:
    client = MagicMock()
    client.chat = AsyncMock(
        return_value=MagicMock(text=text or ""),
        side_effect=error,
    )
    return client


class TestNextCheckinAt:
    def test_high_distress_checks_in_soonest(self) -> None:
        scheduled = next_checkin_at(distress_level=0.9, now=_NOW)
        assert scheduled == _NOW + datetime.timedelta(hours=4)

    def test_medium_distress_checks_in_at_twelve_hours(self) -> None:
        scheduled = next_checkin_at(distress_level=0.6, now=_NOW)
        assert scheduled == _NOW + datetime.timedelta(hours=12)

    def test_low_distress_checks_in_tomorrow(self) -> None:
        scheduled = next_checkin_at(distress_level=0.2, now=_NOW)
        assert scheduled == _NOW + datetime.timedelta(hours=24)

    def test_result_is_timezone_aware(self) -> None:
        assert next_checkin_at(distress_level=0.2, now=_NOW).tzinfo is not None

    def test_morning_preference_snaps_to_eight(self) -> None:
        """Onboarding step 3 previously had no effect at all — every check-in
        used the distress-only offset regardless of what the user picked."""
        scheduled = next_checkin_at(
            distress_level=0.2, preferred_time="morning", now=_NOW
        )
        assert scheduled.hour == 8
        assert scheduled > _NOW

    def test_evening_preference_snaps_to_nineteen(self) -> None:
        scheduled = next_checkin_at(
            distress_level=0.2, preferred_time="evening", now=_NOW
        )
        assert scheduled.hour == 19
        assert scheduled > _NOW

    def test_high_distress_ignores_the_preference(self) -> None:
        scheduled = next_checkin_at(
            distress_level=0.9, preferred_time="morning", now=_NOW
        )
        assert scheduled == _NOW + datetime.timedelta(hours=4)


class TestGenerateCheckinText:
    @pytest.mark.asyncio
    async def test_uses_the_model_text(self) -> None:
        client = _groq("Hey Amiru - how did that exam go in the end?")
        with patch("app.services.checkins.get_groq_client", return_value=client):
            text = await generate_checkin_text(
                user_name="Amiru",
                surface_emotion="nervousness",
                distress_level=0.6,
                session_history=[],
            )
        assert text == "Hey Amiru - how did that exam go in the end?"
        assert client.chat.await_args.kwargs["max_tokens"] == 80

    @pytest.mark.asyncio
    async def test_falls_back_on_failure(self) -> None:
        client = _groq(error=RuntimeError("groq down"))
        with patch("app.services.checkins.get_groq_client", return_value=client):
            text = await generate_checkin_text(
                user_name="Amiru",
                surface_emotion="nervousness",
                distress_level=0.6,
                session_history=[],
            )
        assert text == CHECKIN_FALLBACK_TEXT

    @pytest.mark.asyncio
    async def test_history_is_anonymised_before_reaching_the_model(self) -> None:
        """The V1 agent pasted the last raw user message straight into the
        prompt. A check-in prompt is still a model call, so the same PII
        stripping the chat path applies must apply here."""
        client = _groq("Hey Amiru - how are things?")
        history = [
            {"role": "user", "text": "My supervisor Dr Perera keeps moving my deadline."}
        ]
        with patch("app.services.checkins.get_groq_client", return_value=client):
            await generate_checkin_text(
                user_name="Amiru",
                surface_emotion="nervousness",
                distress_level=0.6,
                session_history=history,
            )
        prompt = client.chat.await_args.kwargs["user_prompt"]
        assert "Dr Perera" not in prompt


class TestScheduleCheckin:
    @staticmethod
    def _db(turns: list[dict], preferences: dict | None = None) -> MagicMock:
        db = MagicMock()
        db.sessions.find_one = AsyncMock(
            return_value={"session_id": "sess_abc", "turns": turns}
        )
        db.user_memory.find_one = AsyncMock(
            return_value={"preferences": preferences or {}}
        )
        db.pending_checkins.update_one = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_writes_one_pending_checkin_per_session(self) -> None:
        db = self._db(
            [
                {"role": "user", "text": "I'm nervous about my exam"},
                {
                    "role": "assistant",
                    "text": "That sounds heavy.",
                    "eos_snapshot": {
                        "surface_emotion": "nervousness",
                        "distress_level": 0.6,
                    },
                },
            ]
        )
        with patch(
            "app.services.checkins.generate_checkin_text",
            new=AsyncMock(return_value="Hey Amiru - how did the exam go?"),
        ):
            scheduled = await schedule_checkin(
                db, session_id="sess_abc", user_id="user_123", user_name="Amiru"
            )

        assert scheduled is not None
        assert scheduled > datetime.datetime.now(datetime.UTC)
        db.pending_checkins.update_one.assert_awaited_once()
        query, update = db.pending_checkins.update_one.await_args.args
        assert query == {"user_id": "user_123", "from_session": "sess_abc"}
        assert update["$set"]["text"] == "Hey Amiru - how did the exam go?"
        assert update["$set"]["scheduled_at"] == scheduled
        # Reconnecting must not re-arm a check-in that was already delivered.
        assert "delivered" not in update["$set"]

    @pytest.mark.asyncio
    async def test_no_assistant_turn_schedules_nothing(self) -> None:
        db = self._db([{"role": "user", "text": "hi"}])
        assert (
            await schedule_checkin(
                db, session_id="sess_abc", user_id="user_123", user_name="Amiru"
            )
            is None
        )
        db.pending_checkins.update_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_memory_depth_nothing_schedules_nothing(self) -> None:
        """A check-in that references the last session is memory recall, so
        the strictest memory setting turns it off too."""
        db = self._db(
            [
                {
                    "role": "assistant",
                    "text": "ok",
                    "eos_snapshot": {"surface_emotion": "calm", "distress_level": 0.1},
                }
            ],
            preferences={"memory_depth": "nothing"},
        )
        assert (
            await schedule_checkin(
                db, session_id="sess_abc", user_id="user_123", user_name="Amiru"
            )
            is None
        )
        db.pending_checkins.update_one.assert_not_awaited()


class TestSendPendingCheckin:
    @pytest.mark.asyncio
    async def test_delivers_and_marks_delivered(self) -> None:
        db = MagicMock()
        db.pending_checkins.find_one = AsyncMock(
            return_value={
                "_id": "checkin_1",
                "text": "Hey Amiru - how are things?",
                "from_session": "sess_abc",
            }
        )
        db.pending_checkins.update_one = AsyncMock()
        conn = MagicMock()
        conn.send_checkin = AsyncMock()

        await send_pending_checkin(db, "user_123", conn)

        conn.send_checkin.assert_awaited_once_with(
            user_id="user_123",
            text="Hey Amiru - how are things?",
            from_session="sess_abc",
        )
        _, update = db.pending_checkins.update_one.await_args.args
        assert update["$set"]["delivered"] is True

    @pytest.mark.asyncio
    async def test_nothing_due_sends_nothing(self) -> None:
        db = MagicMock()
        db.pending_checkins.find_one = AsyncMock(return_value=None)
        db.pending_checkins.update_one = AsyncMock()
        conn = MagicMock()
        conn.send_checkin = AsyncMock()

        await send_pending_checkin(db, "user_123", conn)

        conn.send_checkin.assert_not_awaited()
        db.pending_checkins.update_one.assert_not_awaited()
