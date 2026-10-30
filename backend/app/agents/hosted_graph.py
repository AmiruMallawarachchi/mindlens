"""Hosted LangGraph runtime for MindLens V2.

The graph deliberately has a small, bounded shape.  It keeps the safety gate
deterministic, uses Groq for structured assessment and response generation,
and treats Pinecone and Langfuse as fail-soft infrastructure.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.groq_client import get_groq_client
from app.agents.hosted_graph_result import llm_call_metadata, result_contract
from app.agents.hosted_graph_state import (
    HostedGraphState,
    _base_eos,
    _clean_json,
    _number,
    _recall_context,
    _specialist_context,
    _stage,
)
from app.agents.response_validator import ResponseValidator
from app.agents.safety_gate import CRISIS_TEMPLATES, safety_gate
from app.core.anonymizer import anonymize
from app.core.crisis_resources import CRISIS_RESOURCES
from app.observability import trace_graph
from app.rag.hosted_retriever import get_hosted_retriever
from app.utils.logger import get_logger

logger = get_logger(__name__)


class HostedGraphOrchestrator:
    """Bounded hosted graph with a stable result contract for the WebSocket."""

    def __init__(self) -> None:
        self.validator = ResponseValidator()
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
        await _stage(
            state,
            "safety",
            "Crisis signals found - everything else pauses."
            if result.is_crisis
            else "Safety gate clear.",
        )
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
        recalled, preferences = _recall_context(state)
        state["memory_recalled"] = recalled
        # Settings > General (tone, personality, custom instructions) were
        # stored and returned by recall but never reached the reply prompt, so
        # the controls silently did nothing. They belong on the EOS snapshot
        # and in the specialist's context.
        state["eos"].update(preferences)
        await _stage(
            state,
            "memory",
            f"Recalled {len(recalled)} memory signal(s)." if recalled else "Nothing on file matched this turn.",
        )
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
        context = _specialist_context(state)
        system = (
            f"You are the MindLens {state['route']} specialist. Write one warm, natural reply. "
            "Listen first, reflect the user's point, ask at most one useful question, and offer one practical next step only when it fits. "
            "Honour the user's tone, personality, and custom instructions when they are present. "
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
            text = "I'm with you. Could you tell me a little more about what feels hardest right now?"
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
            state["agent_outputs"] = [
                {
                    "agent": "crisis",
                    "text": text,
                    "metadata": {"resources": CRISIS_RESOURCES},
                }
            ]
            state["route"] = "crisis"
        else:
            report = self.validator.validate(state.get("response", ""))
            if not report.passed:
                state["degraded"].append("response_validation")
                state["response"] = "I'm here with you. Tell me more about what's going on."
        await _stage(state, "finalize", "Response ready.")
        return state

    @staticmethod
    def _result_contract(state: HostedGraphState) -> dict[str, Any]:
        return result_contract(state)

    @staticmethod
    def _llm_call_metadata(stage: str, response: Any) -> dict[str, Any]:
        return llm_call_metadata(stage, response)

_hosted_orchestrator: HostedGraphOrchestrator | None = None


def get_hosted_orchestrator() -> HostedGraphOrchestrator:
    global _hosted_orchestrator
    if _hosted_orchestrator is None:
        _hosted_orchestrator = HostedGraphOrchestrator()
    return _hosted_orchestrator
