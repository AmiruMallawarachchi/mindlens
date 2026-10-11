"""Hosted LangGraph runtime for MindLens V2.

The graph deliberately has a small, bounded shape.  It keeps the safety gate
deterministic, uses Groq for structured assessment and response generation,
and treats Pinecone and Langfuse as fail-soft infrastructure.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.response_assembler import ResponseAssembler
from app.agents.safety_gate import CRISIS_TEMPLATES, safety_gate
from app.agents.groq_client import get_groq_client
from app.core.anonymizer import anonymize
from app.core.emotional_os import EmotionalOperatingState, Modality
from app.observability import trace_graph
from app.rag.hosted_retriever import get_hosted_retriever
from app.utils.logger import get_logger

logger = get_logger(__name__)


class HostedGraphState(TypedDict, total=False):
    user_text: str
    user_name: str
    session_history: list[dict[str, Any]]
    memory: dict[str, Any] | None
    user_id: str | None
    on_stage: Any
    safety: dict[str, Any]
    crisis_flag: bool
    assessment: dict[str, Any]
    eos: dict[str, Any]
    route: str
    rag_chunks: list[str]
    response: str
    agent_outputs: list[dict[str, Any]]
    degraded: list[str]
    memory_recalled: list[str]
    telemetry: dict[str, Any]
    options: dict[str, Any] | None
    graph_nodes: list[str]
    review_required: bool
    llm_calls: list[dict[str, Any]]


def _clean_json(text: str) -> dict[str, Any]:
    """Parse a JSON object from a hosted model response."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Groq returned no JSON object") from None
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Groq returned a non-object JSON value")
    return value


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


async def _stage(state: HostedGraphState, name: str, detail: str) -> None:
    callback = state.get("on_stage")
    if callback:
        await callback(name, detail)


def _base_eos(state: HostedGraphState, assessment: dict[str, Any]) -> dict[str, Any]:
    emotion = str(assessment.get("surface_emotion") or "neutral")
    core = str(assessment.get("core_emotion") or emotion)
    distress = _number(assessment.get("distress_level"), 0.0)
    modality_name = str(assessment.get("modality") or ("DBT" if distress >= 0.7 else "CBT"))
    try:
        modality = Modality(modality_name)
    except ValueError:
        modality = Modality.CBT
    return EmotionalOperatingState(
        surface_emotion=emotion,
        surface_confidence=_number(assessment.get("surface_confidence"), 0.0),
        core_emotion=core,
        suppressed_emotion=assessment.get("suppressed_emotion"),
        distress_level=distress,
        emotional_stability=1.0 - distress,
        mental_fatigue=_number(assessment.get("mental_fatigue"), 0.3),
        modality=modality,
        crisis_escalating=bool(assessment.get("crisis_risk")),
        session_turn_count=len(state.get("session_history", [])),
        valence=str(assessment.get("valence") or "neutral"),
        distortion_label=assessment.get("distortion_label"),
        distortion_score=_number(assessment.get("distortion_score"), 0.0),
    ).model_dump(mode="json")


class HostedGraphOrchestrator:
    """Bounded hosted graph with a stable result contract for the WebSocket."""

    def __init__(self) -> None:
        self.assembler = ResponseAssembler()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(HostedGraphState)
        builder.add_node("safety_gate", self._safety_gate)
        builder.add_node("assess", self._assess)
        builder.add_node("memory_recall", self._memory_recall)
        builder.add_node("retrieve", self._retrieve)
        builder.add_node("specialist", self._specialist)
        builder.add_node("review", self._review)
        builder.add_node("finalize", self._finalize)
        builder.add_edge(START, "safety_gate")
        builder.add_conditional_edges(
            "safety_gate", self._after_safety, {"crisis": "finalize", "assess": "assess"}
        )
        builder.add_conditional_edges(
            "assess", self._after_assessment, {"crisis": "finalize", "continue": "memory_recall"}
        )
        builder.add_edge("memory_recall", "retrieve")
        builder.add_edge("retrieve", "specialist")
        builder.add_conditional_edges(
            "specialist", self._after_specialist, {"review": "review", "finalize": "finalize"}
        )
        builder.add_edge("review", "finalize")
        builder.add_edge("finalize", END)
        return builder.compile()

    async def run_full_pipeline(
        self,
        user_text: str,
        *,
        user_name: str = "friend",
        session_history: list[dict[str, Any]] | None = None,
        rag_chunks: list[str] | None = None,
        user_id: str | None = None,
        memory: dict[str, Any] | None = None,
        on_stage=None,
    ) -> dict[str, Any]:
        state: HostedGraphState = {
            "user_text": user_text,
            "user_name": user_name,
            "session_history": session_history or [],
            "memory": memory,
            "user_id": user_id,
            "on_stage": on_stage,
            "rag_chunks": rag_chunks or [],
            "degraded": [],
            "graph_nodes": [],
            "llm_calls": [],
        }
        trace = trace_graph(state)
        with trace:
            result = await self.graph.ainvoke(state)
            trace.state.update(result)
        return self._result_contract(result)

    @staticmethod
    def _after_safety(state: HostedGraphState) -> str:
        return "crisis" if state.get("crisis_flag") else "assess"

    @staticmethod
    def _after_specialist(state: HostedGraphState) -> str:
        return "review" if state.get("review_required") else "finalize"

    @staticmethod
    def _after_assessment(state: HostedGraphState) -> str:
        return "crisis" if state.get("crisis_flag") else "continue"

    async def _safety_gate(self, state: HostedGraphState) -> HostedGraphState:
        state["graph_nodes"].append("safety_gate")
        result = await safety_gate.evaluate(state["user_text"], state.get("user_id"))
        state["safety"] = result.model_dump(exclude={"user_message_snippet"})
        state["crisis_flag"] = result.is_crisis
        if result.is_crisis:
            state["assessment"] = {"crisis_risk": True, "distress_level": 1.0}
        await _stage(state, "safety", "Crisis signals found — everything else pauses." if result.is_crisis else "Safety gate clear.")
        return state

    async def _assess(self, state: HostedGraphState) -> HostedGraphState:
        state["graph_nodes"].append("assess")
        prompt = {
            "message": anonymize(state["user_text"]),
            "recent_turns": [anonymize(str(t.get("text", ""))) for t in state.get("session_history", [])[-6:]],
        }
        system = (
            "You are MindLens triage. Return only JSON. Never diagnose. "
            "Assess emotion and conversation needs, and set crisis_risk true only for likely immediate self-harm or harm to others. "
            "Schema: surface_emotion, surface_confidence, core_emotion, suppressed_emotion, distress_level, "
            "mental_fatigue, modality, valence, distortion_label, distortion_score, crisis_risk, route, review_required."
        )
        try:
            response = await get_groq_client().chat(
                system_prompt=system,
                user_prompt=json.dumps(prompt, ensure_ascii=False),
                model_tier="70B",
                max_tokens=260,
                temperature=0.1,
            )
            assessment = _clean_json(response.text)
            state["llm_calls"].append(self._llm_call_metadata("assessment", response))
        except Exception as exc:
            logger.warning("Hosted assessment failed: %s", exc)
            state["degraded"].append("assessment")
            assessment = {"surface_emotion": "neutral", "distress_level": 0.0, "route": "empathy", "crisis_risk": False}
        state["assessment"] = assessment
        if bool(assessment.get("crisis_risk")):
            state["crisis_flag"] = True
            state["safety"] = {
                "is_crisis": True,
                "layer_triggered": "hosted_assessment",
                "confidence": _number(assessment.get("crisis_confidence"), 0.8),
                "reason": "Hosted assessment flagged immediate safety risk",
            }
        state["eos"] = _base_eos(state, assessment)
        state["review_required"] = bool(assessment.get("review_required")) or _number(assessment.get("distress_level")) >= 0.7
        await _stage(state, "reading", "Assessment complete.")
        return state

    async def _memory_recall(self, state: HostedGraphState) -> HostedGraphState:
        state["graph_nodes"].append("memory_recall")
        memory = state.get("memory") or {}
        recalled: list[str] = []
        if memory.get("preferences", {}).get("tone_preference"):
            recalled.append("tone preference")
        if memory.get("emotional_patterns", {}).get("trigger_topics"):
            recalled.append("known trigger context")
        state["memory_recalled"] = recalled
        await _stage(state, "memory", f"Recalled {len(recalled)} relevant preference(s)." if recalled else "Nothing on file matched this turn.")
        return state

    async def _retrieve(self, state: HostedGraphState) -> HostedGraphState:
        state["graph_nodes"].append("retrieve")
        if state.get("crisis_flag"):
            state["rag_chunks"] = []
            state["telemetry"] = {"rag": {"status": "skipped_crisis", "chunks": 0}}
        elif len(state["user_text"].split()) < 4 and _number(state.get("assessment", {}).get("distress_level")) < 0.5:
            state["rag_chunks"] = []
            state["telemetry"] = {"rag": {"status": "skipped_trivial", "chunks": 0}}
        elif state.get("rag_chunks"):
            state["telemetry"] = {"rag": {"status": "provided", "chunks": len(state["rag_chunks"])}}
        else:
            try:
                state["rag_chunks"] = await asyncio.to_thread(get_hosted_retriever().retrieve, anonymize(state["user_text"]))
                state["telemetry"] = {"rag": {"status": "ran", "chunks": len(state["rag_chunks"]), "provider": "pinecone"}}
            except Exception as exc:
                logger.warning("Hosted retrieval failed: %s", exc)
                state["rag_chunks"] = []
                state["degraded"].append("pinecone")
                state["telemetry"] = {"rag": {"status": "failed", "chunks": 0}}
        state["telemetry"]["modality"] = state.get("eos", {}).get("modality")
        await _stage(state, "retrieval", f"Prepared {len(state['rag_chunks'])} therapy passage(s).")
        return state

    async def _specialist(self, state: HostedGraphState) -> HostedGraphState:
        state["graph_nodes"].append("specialist")
        route = str(state.get("assessment", {}).get("route") or "empathy").lower()
        allowed = {"empathy", "mindfulness", "journaling", "reflection", "routine", "challenge", "distortion"}
        state["route"] = route if route in allowed else "empathy"
        if state.get("crisis_flag"):
            return state
        context = {
            "message": anonymize(state["user_text"]),
            "history": [anonymize(str(t.get("text", ""))) for t in state.get("session_history", [])[-6:]],
            "memory_signals": state.get("memory_recalled", []),
            "therapy_notes": state.get("rag_chunks", [])[:5],
            "assessment": state.get("assessment", {}),
        }
        system = (
            f"You are the MindLens {state['route']} specialist. Write one warm, natural reply. "
            "Listen first, reflect the user's point, ask at most one useful question, and offer one practical next step only when it fits. "
            "Never diagnose, prescribe, claim certainty, or mention internal agents. Return only the reply text."
        )
        try:
            response = await get_groq_client().chat(
                system_prompt=system,
                user_prompt=json.dumps(context, ensure_ascii=False),
                model_tier="70B" if state.get("review_required") else "8B",
                max_tokens=420,
                temperature=0.55,
            )
            text = response.text.strip()
            state["llm_calls"].append(self._llm_call_metadata("specialist", response))
        except Exception as exc:
            logger.warning("Hosted specialist failed: %s", exc)
            state["degraded"].append("specialist")
            text = "I’m with you. Could you tell me a little more about what feels hardest right now?"
        state["response"] = text
        state["agent_outputs"] = [{"agent": state["route"], "text": text, "metadata": {"provider": "groq"}}]
        await _stage(state, "approach", f"The {state['route']} specialist prepared a response.")
        return state

    async def _review(self, state: HostedGraphState) -> HostedGraphState:
        state["graph_nodes"].append("review")
        prompt = json.dumps({"reply": state.get("response", ""), "assessment": state.get("assessment", {})}, ensure_ascii=False)
        try:
            response = await get_groq_client().chat(
                system_prompt="Review this MindLens reply. Return only JSON with keys approved and replacement. Approve unless it diagnoses, prescribes, minimizes, or encourages harm. If not approved, replacement must be a safe warm reply.",
                user_prompt=prompt,
                model_tier="70B",
                max_tokens=180,
                temperature=0.0,
            )
            verdict = _clean_json(response.text)
            state["llm_calls"].append(self._llm_call_metadata("review", response))
            if not bool(verdict.get("approved", True)) and isinstance(verdict.get("replacement"), str):
                state["response"] = verdict["replacement"].strip()
        except Exception as exc:
            logger.warning("Hosted review failed: %s", exc)
            state["degraded"].append("review")
        await _stage(state, "review", "Reply safety review complete.")
        return state

    async def _finalize(self, state: HostedGraphState) -> HostedGraphState:
        state["graph_nodes"].append("finalize")
        if state.get("crisis_flag"):
            distress = _number(state.get("assessment", {}).get("distress_level"), 1.0)
            text = CRISIS_TEMPLATES["severe" if distress >= 0.85 else "moderate"]
            state["response"] = text
            from app.agents.crisis_agent import CRISIS_RESOURCES

            state["agent_outputs"] = [{"agent": "crisis", "text": text, "metadata": {"resources": CRISIS_RESOURCES}}]
            state["route"] = "crisis"
        else:
            report = self.assembler._validator.validate(state.get("response", ""))
            if not report.passed:
                state["degraded"].append("response_validation")
                state["response"] = "I’m here with you. Tell me more about what’s going on."
        await _stage(state, "finalize", "Response ready.")
        return state

    @staticmethod
    def _result_contract(state: HostedGraphState) -> dict[str, Any]:
        crisis = bool(state.get("crisis_flag"))
        agents = ["crisis"] if crisis else [state.get("route", "empathy")]
        return {
            "eos": state.get("eos", EmotionalOperatingState().model_dump(mode="json")),
            "agents": agents,
            "crisis_flag": crisis,
            "assembled_text": state.get("response", ""),
            "agent_outputs": state.get("agent_outputs", []),
            "safety": state.get("safety", {"is_crisis": False}),
            "degraded": sorted(set(state.get("degraded", []))),
            "memory_recalled": state.get("memory_recalled", []),
            "options": None,
            "telemetry": {
                **state.get("telemetry", {}),
                "graph": {"nodes": state.get("graph_nodes", []), "route": state.get("route", "empathy")},
                "llm": {
                    "calls": state.get("llm_calls", []),
                    "count": len(state.get("llm_calls", [])),
                },
                "substantive": len(state.get("user_text", "").split()) >= 4,
            },
        }

    @staticmethod
    def _llm_call_metadata(stage: str, response: Any) -> dict[str, Any]:
        """Keep provider telemetry JSON-safe and free of prompts or outputs."""
        def safe_number(value: Any) -> int | None:
            return value if isinstance(value, int | float) else None

        return {
            "stage": stage,
            "model": str(getattr(response, "model_used", "unknown")),
            "tokens": safe_number(getattr(response, "tokens_used", None)),
            "latency_ms": safe_number(getattr(response, "latency_ms", None)),
        }


_hosted_orchestrator: HostedGraphOrchestrator | None = None


def get_hosted_orchestrator() -> HostedGraphOrchestrator:
    global _hosted_orchestrator
    if _hosted_orchestrator is None:
        _hosted_orchestrator = HostedGraphOrchestrator()
    return _hosted_orchestrator
