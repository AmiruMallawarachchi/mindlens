"""Safety screening, model inference, and EOS construction."""

from __future__ import annotations

from typing import Any, Literal

from app.agents.groq_client import _record_degradation
from app.agents.safety_gate import SafetyGateResult
from app.core.anonymizer import anonymize
from app.core.emotion_labels import EMOTION_LABELS, POSITIVE_EMOTIONS, is_negative
from app.core.emotional_os import EmotionalOperatingState, Modality
from app.utils.logger import get_logger
from .shared import DISTORTION_LABEL_MAP, turn_is_substantive

logger = get_logger("app.agents.orchestrator")

class OrchestratorTurnMixin:
    async def process_turn(
        self, user_text: str, *, user_id: str | None = None, session_turn_count: int = 0
    ) -> dict[str, Any]:
        """
        1. Run all four classifiers concurrently.
        2. Parse outputs into structured scores.
        3. Build EOS state.
        4. Return routing decision + EOS snapshot.

        `session_turn_count` is how many turns this session already holds. It
        must be supplied: three agents in `_select_agents` are gated on it
        (personality > 2, progress every 5, checkin_scheduler every 3), and
        while it defaulted to 0 on every real turn none of the three could
        ever be selected.
        """
        safety_result = await self._safety.evaluate(user_text, user_id=user_id)
        if safety_result.is_crisis:
            eos = EmotionalOperatingState(
                surface_emotion="distress",
                core_emotion="hopelessness",
                distress_level=1.0,
                emotional_stability=0.0,
                crisis_escalating=True,
                modality=Modality.DBT,
            )
            return {
                # mode="json": eos carries PeopleGraph.mentioned_at and other
            # datetime fields that don't survive a plain model_dump() into
            # the WebSocket send_json() call downstream — see
            # EmotionalOperatingState.to_dict()'s docstring.
            "eos": eos.model_dump(mode="json"),
                "agents": ["crisis"],
                "crisis_flag": True,
                "safety": safety_result.model_dump(exclude={"user_message_snippet"}),
            }

        model_text = anonymize(user_text)
        raw_results = await self.models.predict_all(model_text)

        # predict_all swallows a per-model failure into an empty list so one
        # dead classifier can't fail the turn. That's the right call, but it
        # left no trace: a turn where the *crisis* classifier was down looked
        # byte-identical to a healthy one, because _parse_crisis maps empty
        # output to ("UNKNOWN", 0.0) and crisis_flag stays False. The regex
        # gate above still ran — that layer is unconditional — but the second
        # layer being silently absent is exactly the thing an operator needs
        # told. Record it the same way LLM fallbacks are recorded, so it
        # reaches /ready's health status and the thinking panel.
        for _model_name, _output in raw_results.items():
            if not _output:
                _record_degradation(f"model:{_model_name}")
                if _model_name == "crisis":
                    logger.error(
                        "Crisis classifier returned no output — this turn was "
                        "screened by the regex gate alone."
                    )

        # Parse emotion (28-class multi-label)
        emotion_scores = self._parse_multilabel(raw_results["emotion"], EMOTION_LABELS)
        surface_emotion = self._argmax(emotion_scores)
        core_emotion = self._pick_core_emotion(emotion_scores)
        suppressed_emotion = self._pick_suppressed(emotion_scores, surface_emotion)

        # Parse crisis (binary)
        crisis_label, crisis_score = self._parse_crisis(raw_results.get("crisis", []))
        crisis_flag = crisis_label in {
            "CRISIS",
            "LABEL_1",
            "SUICIDAL_IDEATION",
            "SELF_HARM",
            "HIGH_RISK",
        } and crisis_score > 0.45
        if crisis_flag:
            safety_result = SafetyGateResult(
                is_crisis=True,
                layer_triggered="classifier",
                confidence=crisis_score,
                reason="Crisis classifier threshold exceeded",
                user_message_snippet="",
            )

        # Parse mental health (multi-label)
        mh_label_map = {
            "LABEL_0": "depression",
            "LABEL_1": "anxiety",
            "LABEL_2": "stress",
            "LABEL_3": "burnout",
            "LABEL_4": "ptsd",
        }
        mh_scores = self._parse_multilabel(raw_results["mental_health"], mh_label_map)
        distortion_scores = self._parse_multilabel(
            raw_results.get("distortion", []), DISTORTION_LABEL_MAP
        )
        distortion_label = self._argmax(distortion_scores)
        distortion_score = distortion_scores.get(distortion_label, 0.0)
        if distortion_score < 0.45:
            distortion_label = None
            distortion_score = 0.0

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
            # The classifier's actual score for the winning label. This was
            # never assigned, so every turn kept the field's 0.8 default —
            # and that constant was shown to the user as "how confident the
            # emotion model is in this read" (emotion-read.tsx), narrated in
            # the thinking panel ("at 0.80 confidence"), fed to the empathy
            # agent's prompt, and used to scale the room's intensity. A
            # fabricated number presented as a measurement, on the one figure
            # the product uses to justify "a read, never a diagnosis".
            surface_confidence=round(emotion_scores.get(surface_emotion, 0.0), 3),
            distress_level=round(distress_level, 3),
            crisis_escalating=crisis_flag,
            valence=valence,
            modality=modality,
            trust_level=0.5,
            session_depth=0.0,
            distortion_label=distortion_label,
            distortion_score=round(distortion_score, 3),
            session_turn_count=session_turn_count,
        )

        # Routing decision. process_turn does its own substance check —
        # it is a separate entry point from run_full_pipeline and has no
        # access to that one's local.
        agents = self._select_agents(
            eos,
            crisis_flag,
            substantive=turn_is_substantive(user_text, eos.distress_level),
        )

        # Synchronize run flags based on agents
        eos.run_mindfulness = "mindfulness" in agents
        eos.run_challenge = "challenge" in agents
        eos.run_journaling = "journaling" in agents
        eos.run_distortion = "distortion" in agents
        eos.run_routine = "routine" in agents

        return {
            # mode="json": eos carries PeopleGraph.mentioned_at and other
            # datetime fields that don't survive a plain model_dump() into
            # the WebSocket send_json() call downstream — see
            # EmotionalOperatingState.to_dict()'s docstring.
            "eos": eos.model_dump(mode="json"),
            "agents": agents,
            "crisis_flag": crisis_flag,
            "safety": safety_result.model_dump(exclude={"user_message_snippet"}),
        }
