"""Unit tests for the memory recall module."""

from __future__ import annotations

import pytest
from app.core.memory_recall import MemoryRecall, recall_for_turn


class TestRecallForTurn:
    """Validate memory recall behaviour."""

    def test_no_memory_returns_empty(self) -> None:
        recall = recall_for_turn(
            None, user_text="hello", surface_emotion="joy", core_emotion="joy"
        )
        assert recall == MemoryRecall()

    def test_people_graph_built_from_doc(self) -> None:
        memory = {
            "people": {
                "Ravi": {"role": "best friend", "context": "same exam", "sentiment": "positive"},
            }
        }
        recall = recall_for_turn(
            memory, user_text="just chatting", surface_emotion="joy", core_emotion="joy"
        )
        assert len(recall.people_graph) == 1
        assert recall.people_graph[0].name == "Ravi"
        assert recall.people_graph[0].relationship == "best friend"

    def test_person_mentioned_by_name_is_recalled(self) -> None:
        memory = {
            "people": {
                "Ravi": {"role": "best friend", "context": "same exam", "sentiment": "positive"},
            }
        }
        recall = recall_for_turn(
            memory,
            user_text="I talked to Ravi about it today",
            surface_emotion="joy",
            core_emotion="joy",
        )
        assert any("Ravi" in item for item in recall.memory_recalled)

    def test_person_not_mentioned_is_not_recalled(self) -> None:
        memory = {
            "people": {
                "Ravi": {"role": "best friend", "context": "same exam", "sentiment": "positive"},
            }
        }
        recall = recall_for_turn(
            memory,
            user_text="just a normal day",
            surface_emotion="joy",
            core_emotion="joy",
        )
        assert recall.memory_recalled == []

    def test_trigger_topic_match(self) -> None:
        memory = {
            "emotional_patterns": {
                "trigger_topics": ["exams", "sleep"],
            }
        }
        recall = recall_for_turn(
            memory,
            user_text="I couldn't focus because of the exams coming up",
            surface_emotion="fear",
            core_emotion="fear",
        )
        assert any("Exams" in item for item in recall.memory_recalled)

    def test_trigger_topic_no_match(self) -> None:
        memory = {
            "emotional_patterns": {
                "trigger_topics": ["exams", "sleep"],
            }
        }
        recall = recall_for_turn(
            memory,
            user_text="had a nice walk today",
            surface_emotion="joy",
            core_emotion="joy",
        )
        assert recall.memory_recalled == []

    def test_common_emotion_continuity(self) -> None:
        memory = {"emotional_patterns": {"most_common_emotion": "fear"}}
        recall = recall_for_turn(
            memory, user_text="text", surface_emotion="fear", core_emotion="fear"
        )
        assert any("Fear" in item for item in recall.memory_recalled)

    def test_common_emotion_no_match_is_silent(self) -> None:
        memory = {"emotional_patterns": {"most_common_emotion": "fear"}}
        recall = recall_for_turn(
            memory, user_text="text", surface_emotion="joy", core_emotion="joy"
        )
        assert recall.memory_recalled == []

    def test_coping_surfaced_only_under_distress(self) -> None:
        memory = {"emotional_patterns": {"effective_coping": ["breathing", "music"]}}

        distressed = recall_for_turn(
            memory, user_text="text", surface_emotion="sadness", core_emotion="sadness"
        )
        assert any("Breathing" in item for item in distressed.memory_recalled)

        calm = recall_for_turn(
            memory, user_text="text", surface_emotion="joy", core_emotion="joy"
        )
        assert calm.memory_recalled == []

    def test_preferred_modality_passed_through(self) -> None:
        memory = {"preferences": {"preferred_modality": "DBT"}}
        recall = recall_for_turn(
            memory, user_text="text", surface_emotion="joy", core_emotion="joy"
        )
        assert recall.preferred_modality == "DBT"

    def test_malformed_people_shape_is_ignored(self) -> None:
        memory = {"people": ["not", "a", "dict"]}
        recall = recall_for_turn(
            memory, user_text="text", surface_emotion="joy", core_emotion="joy"
        )
        assert recall.people_graph == []

    # -----------------------------------------------------------------------
    # T2 — the standing social profile
    # -----------------------------------------------------------------------

    def test_introvert_score_read_from_preferences(self) -> None:
        memory = {"preferences": {"introvert_score": 0.2}}
        recall = recall_for_turn(
            memory, user_text="text", surface_emotion="joy", core_emotion="joy"
        )
        assert recall.introvert_score == 0.2

    def test_absent_introvert_score_is_none_not_a_default(self) -> None:
        """None means 'never inferred', which is not the same as a real 0.5."""
        recall = recall_for_turn(
            {"preferences": {}}, user_text="t", surface_emotion="joy", core_emotion="joy"
        )
        assert recall.introvert_score is None

    @pytest.mark.parametrize("bad", ["0.4", None, True, -0.1, 1.4, {"v": 0.3}])
    def test_malformed_introvert_score_is_ignored(self, bad: object) -> None:
        memory = {"preferences": {"introvert_score": bad}}
        recall = recall_for_turn(
            memory, user_text="t", surface_emotion="joy", core_emotion="joy"
        )
        assert recall.introvert_score is None

    def test_memory_depth_nothing_withholds_the_inferred_score(self) -> None:
        """Nobody typed this score — MindLens inferred it from past sessions,
        so applying it under "nothing" would contradict the control."""
        memory = {
            "preferences": {"introvert_score": 0.2, "memory_depth": "nothing"},
        }
        recall = recall_for_turn(
            memory, user_text="text", surface_emotion="joy", core_emotion="joy"
        )
        assert recall.introvert_score is None

    def test_memory_depth_key_details_keeps_the_score(self) -> None:
        memory = {
            "preferences": {"introvert_score": 0.2, "memory_depth": "key_details"},
        }
        recall = recall_for_turn(
            memory, user_text="text", surface_emotion="joy", core_emotion="joy"
        )
        assert recall.introvert_score == 0.2
