"""Classifier output parsing, distress scoring, and agent routing policy."""

from __future__ import annotations

from typing import Any

from app.core.emotion_labels import EMOTION_SEVERITY_WEIGHTS, NEGATIVE_EMOTIONS
from app.core.emotional_os import EmotionalOperatingState, Modality

class OrchestratorScoringMixin:
    @staticmethod
    def _parse_multilabel(
        pipeline_output: list[Any],
        label_map: dict[str, str],
    ) -> dict[str, float]:
        """
        Convert HF multi-label output into {canonical_name: score}.
        pipeline_output may be list[dict] or list[list[dict]] depending on batching.
        """
        scores: dict[str, float] = {}
        flat: list[dict[str, Any]] = []

        for item in pipeline_output:
            if isinstance(item, list):
                for sub in item:
                    if isinstance(sub, dict):
                        flat.append(sub)
            elif isinstance(item, dict):
                flat.append(item)

        for entry in flat:
            raw_label = str(entry.get("label", ""))
            score = float(entry.get("score", 0.0))
            canonical = label_map.get(raw_label, raw_label)
            scores[canonical] = score
        return scores
    @staticmethod
    def _argmax(scores: dict[str, float]) -> str:
        """Return key with highest value. Empty dict returns 'neutral'."""
        if not scores:
            return "neutral"
        return max(scores, key=lambda k: scores[k])
    @staticmethod
    def _parse_crisis(pipeline_output: list[Any]) -> tuple[str, float]:
        """Normalize nested and model-specific crisis classifier outputs."""
        flat: list[dict[str, Any]] = []
        for item in pipeline_output:
            if isinstance(item, list):
                flat.extend(entry for entry in item if isinstance(entry, dict))
            elif isinstance(item, dict):
                flat.append(item)
        if not flat:
            return "UNKNOWN", 0.0
        best = max(flat, key=lambda item: float(item.get("score", 0.0)))
        label = str(best.get("label", "UNKNOWN")).upper()
        score = float(best.get("score", 0.0))
        if label in {"NON_CRISIS", "LABEL_0", "SAFE", "NOT_CRISIS"}:
            score = 1.0 - score
        return label, max(0.0, min(score, 1.0))
    @staticmethod
    def _pick_core_emotion(scores: dict[str, float]) -> str:
        """Highest-scoring NEGATIVE emotion; fallback to overall highest."""
        negative = {k: v for k, v in scores.items() if k in NEGATIVE_EMOTIONS}
        if negative:
            return max(negative, key=lambda k: negative[k])
        return OrchestratorScoringMixin._argmax(scores)
    @staticmethod
    def _pick_suppressed(scores: dict[str, float], surface: str) -> str:
        """Second-highest emotion overall."""
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for label, _ in sorted_scores:
            if label != surface:
                return label
        return surface
    @staticmethod
    def _compute_distress(
        emotion_scores: dict[str, float],
        mh_scores: dict[str, float],
        crisis_score: float,
    ) -> float:
        """
        Weighted composite:
            40% max negative emotion severity
            25% max MH condition score
            35% crisis score
        """
        max_neg = max(
            (
                emotion_scores.get(e, 0.0) * EMOTION_SEVERITY_WEIGHTS.get(e, 1.0)
                for e in NEGATIVE_EMOTIONS
            ),
            default=0.0,
        )
        max_mh = max(mh_scores.values()) if mh_scores else 0.0
        return (max_neg * 0.40) + (max_mh * 0.25) + (crisis_score * 0.35)
    @staticmethod
    def _select_agents(
        eos: EmotionalOperatingState, crisis_flag: bool, *, substantive: bool = True
    ) -> list[str]:
        """
        Cost-optimized agent dispatch.
        $0 agents run every turn; paid agents gated by thresholds.
        """
        if crisis_flag:
            return ["crisis"]

        agents: list[str] = ["empathy"]

        # The opening turn asks a question; it does not prescribe.
        #
        # Empathy's job on turn one is to find out what's going on. A
        # specialist firing alongside it answers a question the user has not
        # had a chance to reply to yet — someone who said they were putting
        # off their project got a five-step grounding script in the same
        # breath as "what's holding you back?". Let empathy open alone and
        # give them a turn to answer.
        #
        # High distress overrides this: grounding someone who is struggling
        # matters more than conversational shape.
        opening_turn = eos.session_turn_count == 0 and eos.distress_level < 0.7
        # A filler turn gets the same treatment as an opening one: nobody
        # wants an exercise in response to "ok thanks".
        held_back = opening_turn or not substantive

        # Safety-critical: mindfulness for high distress, or for anxious
        # emotions that are actually running warm.
        #
        # The emotion arm used to be unconditional — any turn the classifier
        # labelled anxiety/fear/nervousness got a breathing exercise,
        # however mild, and mentioning an exam in passing was enough. Once
        # the classifiers were fixed and started returning real labels, that
        # meant an exercise on nearly every turn: the same guided script
        # again and again in place of the app getting to know the person.
        # Requiring a moderate distress floor alongside the label keeps the
        # exercise for the turns that warrant one, while the high-distress
        # arm above is untouched so genuine distress still always grounds.
        if not held_back and (
            eos.distress_level > 0.5
            or (
                eos.core_emotion in {"anxiety", "fear", "nervousness"}
                and eos.distress_level > 0.35
            )
        ):
            agents.append("mindfulness")

        # Reflection for meaningful session depth
        if not held_back and eos.session_depth >= 0.3:
            agents.append("reflection")

        # Challenge: only when trust is high and not in crisis
        if not held_back and eos.trust_level >= 0.6 and eos.emotional_stability >= 0.5 and not eos.is_in_crisis():
            agents.append("challenge")

        # Distortion: when CBT modality is active
        if not held_back and eos.modality == Modality.CBT:
            agents.append("distortion")

        # Routine: when fatigue is high
        if not held_back and eos.mental_fatigue >= 0.7:
            agents.append("routine")

        # Journaling: when stable enough and receptive
        if not held_back and eos.emotional_stability >= 0.3 and eos.mental_fatigue < 0.8 and eos.is_receptive_to("journaling"):
            agents.append("journaling")

        # Progress: periodic insight (every 5 turns or at end of session)
        if eos.session_turn_count > 0 and eos.session_turn_count % 5 == 0:
            agents.append("progress")

        # Personality: tone adaptation (invisible, runs for context)
        if eos.session_turn_count > 2:
            agents.append("personality")

        # Check-in scheduler: background job scheduling
        if eos.session_turn_count > 0 and eos.session_turn_count % 3 == 0:
            agents.append("checkin_scheduler")

        # Session memory save: always runs at end of turn
        agents.append("session_memory_save")

        return agents
