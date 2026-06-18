"""
MindLens Orchestrator
=====================
Builds the Emotional Operating System (EOS) state and routes to agents.
All model inference runs in parallel via asyncio.gather.
"""

from __future__ import annotations

from typing import Any, Literal

from app.core.emotion_labels import (
    EMOTION_LABELS,
    EMOTION_SEVERITY_WEIGHTS,
    NEGATIVE_EMOTIONS,
    POSITIVE_EMOTIONS,
    is_negative,
)
from app.core.emotional_os import (
    EmotionalOperatingState,
    Modality,
)
from app.models.loader import ModelManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """
    Central router. Receives user text, runs safety + models in parallel,
    constructs EOS snapshot, and decides which agents to invoke.
    """

    def __init__(self) -> None:
        self.models = ModelManager()

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    async def process_turn(self, user_text: str) -> dict[str, Any]:
        """
        1. Run all three classifiers concurrently.
        2. Parse outputs into structured scores.
        3. Build EOS state.
        4. Return routing decision + EOS snapshot.
        """
        raw_results = await self.models.predict_all(user_text)

        # Parse emotion (28-class multi-label)
        emotion_scores = self._parse_multilabel(raw_results["emotion"], EMOTION_LABELS)
        surface_emotion = self._argmax(emotion_scores)
        core_emotion = self._pick_core_emotion(emotion_scores)
        suppressed_emotion = self._pick_suppressed(emotion_scores, surface_emotion)

        # Parse crisis (binary)
        crisis_result = raw_results["crisis"][0]
        crisis_label = str(crisis_result.get("label", "NON_CRISIS")).upper()
        crisis_score = float(crisis_result.get("score", 0.0))
        crisis_flag = crisis_label == "CRISIS" and crisis_score > 0.45

        # Parse mental health (multi-label)
        mh_label_map = {
            "LABEL_0": "depression",
            "LABEL_1": "anxiety",
            "LABEL_2": "stress",
            "LABEL_3": "burnout",
            "LABEL_4": "ptsd",
        }
        mh_scores = self._parse_multilabel(raw_results["mental_health"], mh_label_map)

        # Compute composite distress
        distress_level = self._compute_distress(emotion_scores, mh_scores, crisis_score)

        # Determine valence
        valence: Literal["positive", "negative", "neutral"] = "neutral"
        if is_negative(core_emotion):
            valence = "negative"
        elif core_emotion in POSITIVE_EMOTIONS:
            valence = "positive"

        # Determine modality
        modality: Modality = Modality.CBT
        if distress_level > 0.7:
            modality = Modality.DBT

        # Build EOS snapshot
        eos = EmotionalOperatingState(
            surface_emotion=surface_emotion,
            core_emotion=core_emotion,
            suppressed_emotion=suppressed_emotion,
            distress_level=round(distress_level, 3),
            valence=valence,
            modality=modality,
            trust_level=0.5,
            session_depth=0.0,
        )

        # Routing decision
        agents = self._select_agents(eos, crisis_flag)

        # Synchronize run flags based on agents
        eos.run_mindfulness = "mindfulness" in agents
        eos.run_music = "music" in agents
        eos.run_challenge = "challenge" in agents
        eos.run_journaling = "reflection" in agents

        return {
            "eos": eos.model_dump(),
            "agents": agents,
            "crisis_flag": crisis_flag,
        }

    # -----------------------------------------------------------------------
    # Parsing helpers
    # -----------------------------------------------------------------------

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
    def _pick_core_emotion(scores: dict[str, float]) -> str:
        """Highest-scoring NEGATIVE emotion; fallback to overall highest."""
        negative = {k: v for k, v in scores.items() if k in NEGATIVE_EMOTIONS}
        if negative:
            return max(negative, key=lambda k: negative[k])
        return Orchestrator._argmax(scores)

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

    # -----------------------------------------------------------------------
    # Agent routing
    # -----------------------------------------------------------------------

    @staticmethod
    def _select_agents(eos: EmotionalOperatingState, crisis_flag: bool) -> list[str]:
        """
        Cost-optimized agent dispatch.
        $0 agents run every turn; paid agents gated by thresholds.
        """
        agents: list[str] = ["empathy"]

        if eos.distress_level > 0.5 or eos.core_emotion in {"anxiety", "fear", "nervousness"}:
            agents.append("mindfulness")

        if eos.distress_level > 0.4:
            agents.append("music")

        if eos.distress_level > 0.3:
            agents.append("reflection")

        trust_level = 0.5
        if trust_level > 0.6 and eos.distress_level < 0.7:
            agents.append("challenge")

        if crisis_flag:
            return ["crisis"]

        return agents
