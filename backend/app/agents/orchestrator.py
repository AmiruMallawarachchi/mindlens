"""
MindLens Orchestrator
=====================
Builds the Emotional Operating System (EOS) state and routes to agents.
All model inference runs in parallel via asyncio.gather.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from app.agents.base_agent import AgentContext, AgentOutput, get_registry
from app.agents.challenge_agent import ChallengeAgent
from app.agents.checkin_agent import CheckInAgent
from app.agents.checkin_scheduler import CheckInScheduler
from app.agents.crisis_agent import CrisisAgent
from app.agents.distortion_agent import DistortionAgent
from app.agents.empathy_agent import EmpathyAgent
from app.agents.groq_client import begin_degradation_tracking
from app.agents.journaling_agent import JournalingAgent
from app.agents.mindfulness_agent import MindfulnessAgent
from app.agents.music_agent import MusicAgent
from app.agents.personality_agent import PersonalityAgent
from app.agents.progress_agent import ProgressAgent
from app.agents.reflection_agent import ReflectionAgent
from app.agents.response_assembler import ResponseAssembler
from app.agents.routine_agent import RoutineAgent
from app.agents.safety_gate import SafetyGateResult, safety_gate
from app.agents.session_memory_save import SessionMemorySave
from app.core.anonymizer import anonymize
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
from app.rag.retriever import get_retriever
from app.utils.logger import get_logger

logger = get_logger(__name__)

DISTORTION_LABEL_MAP = {
    "LABEL_0": "catastrophizing",
    "LABEL_1": "mind_reading",
    "LABEL_2": "all_or_nothing",
    "LABEL_3": "personalization",
    "LABEL_4": "overgeneralization",
    "LABEL_5": "emotional_reasoning",
    "LABEL_6": "should_statements",
    "LABEL_7": "jumping_to_conclusions",
    "LABEL_8": "magnification",
    "LABEL_9": "mental_filter",
}


class Orchestrator:
    """
    Central router. Receives user text, runs safety + models in parallel,
    constructs EOS snapshot, and decides which agents to invoke.
    """

    def __init__(self) -> None:
        self.models = ModelManager()
        self._safety = safety_gate
        self._assembler = ResponseAssembler()
        self._retriever = get_retriever()
        self._init_registry()

    def _init_registry(self) -> None:
        """Register all 14 agents in the global registry."""
        registry = get_registry()
        if not registry.list_names():
            agents = [
                EmpathyAgent(),
                MindfulnessAgent(),
                CrisisAgent(),
                ReflectionAgent(),
                ChallengeAgent(),
                DistortionAgent(),
                RoutineAgent(),
                JournalingAgent(),
                MusicAgent(),
                CheckInAgent(),
                ProgressAgent(),
                PersonalityAgent(),
                CheckInScheduler(),
                SessionMemorySave(),
            ]
            for agent in agents:
                registry.register(agent)
            logger.info("Registered %d agents in orchestrator", len(agents))

    # -----------------------------------------------------------------------
    # Full pipeline: model inference + agent execution + response assembly
    # -----------------------------------------------------------------------

    async def run_full_pipeline(
        self,
        user_text: str,
        *,
        user_name: str = "friend",
        session_history: list[dict] | None = None,
        rag_chunks: list[str] | None = None,
        user_id: str | None = None,
    ) -> dict:
        """
        Complete turn pipeline:
        1. Run model inference → build EOS
        2. Retrieve RAG context (if not provided)
        3. Select agents based on EOS
        4. Run all agents in parallel
        5. Assemble response
        6. Return full result with assembled text
        """
        # Track LLM fallbacks for the whole turn, across every agent.
        degradation = begin_degradation_tracking()

        # Step 1: Model inference + EOS
        turn_result = await self.process_turn(user_text, user_id=user_id)
        eos = EmotionalOperatingState(**turn_result["eos"])
        agent_names = turn_result["agents"]
        crisis_flag = turn_result["crisis_flag"]

        # Step 2: Retrieve RAG context if not provided
        if rag_chunks is None and not crisis_flag:
            try:
                rag_chunks = await asyncio.to_thread(
                    self._retriever.retrieve, anonymize(user_text), eos
                )
            except Exception as exc:
                logger.warning("RAG retrieval failed: %s", exc)
                rag_chunks = []
        elif crisis_flag:
            # Crisis: skip RAG, use crisis protocols directly
            rag_chunks = []

        # Step 3: Build agent context
        ctx = AgentContext(
            eos=eos,
            user_text=anonymize(user_text),
            user_name=user_name,
            session_history=session_history or [],
            rag_chunks=rag_chunks or [],
        )

        # Step 3: Run agents in parallel
        outputs: list[AgentOutput] = []
        if crisis_flag:
            # Crisis mode: only crisis agent
            crisis_agent = get_registry().get("crisis")
            if crisis_agent:
                output = await crisis_agent.run(ctx)
                if output:
                    outputs.append(output)
        else:
            # Normal mode: run selected agents concurrently
            tasks = []
            for name in agent_names:
                agent = get_registry().get(name)
                if agent:
                    tasks.append(agent.run(ctx))
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, AgentOutput):
                        outputs.append(result)
                    elif isinstance(result, Exception):
                        logger.error("Agent failed: %s", result)

        # Step 4: Assemble response
        assembled_text = self._assembler.assemble(
            outputs,
            in_crisis=crisis_flag,
            user_name=user_name,
        )

        return {
            "eos": eos.model_dump(),
            "agents": agent_names,
            "crisis_flag": crisis_flag,
            "assembled_text": assembled_text,
            "agent_outputs": [
                {"agent": o.agent_name, "text": o.text, "metadata": o.metadata}
                for o in outputs
            ],
            "safety": turn_result["safety"],
            # Non-empty when any agent served fallback text instead of model
            # output. Surfaced in the thinking panel so a degraded turn is never
            # mistaken for a working one.
            "degraded": sorted(degradation),
        }

    # -----------------------------------------------------------------------
    # Public entry point (backward compatible)
    # -----------------------------------------------------------------------

    async def process_turn(
        self, user_text: str, *, user_id: str | None = None
    ) -> dict[str, Any]:
        """
        1. Run all four classifiers concurrently.
        2. Parse outputs into structured scores.
        3. Build EOS state.
        4. Return routing decision + EOS snapshot.
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
                "eos": eos.model_dump(),
                "agents": ["crisis"],
                "crisis_flag": True,
                "safety": safety_result.model_dump(exclude={"user_message_snippet"}),
            }

        model_text = anonymize(user_text)
        raw_results = await self.models.predict_all(model_text)

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
        if distortion_scores.get(distortion_label, 0.0) < 0.45:
            distortion_label = None

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
            crisis_escalating=crisis_flag,
            valence=valence,
            modality=modality,
            trust_level=0.5,
            session_depth=0.0,
            distortion_label=distortion_label,
        )

        # Routing decision
        agents = self._select_agents(eos, crisis_flag)

        # Synchronize run flags based on agents
        eos.run_mindfulness = "mindfulness" in agents
        eos.run_music = "music" in agents
        eos.run_challenge = "challenge" in agents
        eos.run_journaling = "journaling" in agents
        eos.run_distortion = "distortion" in agents
        eos.run_routine = "routine" in agents

        return {
            "eos": eos.model_dump(),
            "agents": agents,
            "crisis_flag": crisis_flag,
            "safety": safety_result.model_dump(exclude={"user_message_snippet"}),
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
        if crisis_flag:
            return ["crisis"]

        agents: list[str] = ["empathy"]

        # Safety-critical: mindfulness for high distress or anxiety
        if eos.distress_level > 0.5 or eos.core_emotion in {"anxiety", "fear", "nervousness"}:
            agents.append("mindfulness")

        # Music for moderate distress or music-receptive users
        if eos.distress_level > 0.4 or eos.is_receptive_to("music"):
            agents.append("music")

        # Reflection for meaningful session depth
        if eos.session_depth >= 0.3:
            agents.append("reflection")

        # Challenge: only when trust is high and not in crisis
        if eos.trust_level >= 0.6 and eos.emotional_stability >= 0.5 and not eos.is_in_crisis():
            agents.append("challenge")

        # Distortion: when CBT modality is active
        if eos.modality == Modality.CBT:
            agents.append("distortion")

        # Routine: when fatigue is high
        if eos.mental_fatigue >= 0.7:
            agents.append("routine")

        # Journaling: when stable enough and receptive
        if eos.emotional_stability >= 0.3 and eos.mental_fatigue < 0.8 and eos.is_receptive_to("journaling"):
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
