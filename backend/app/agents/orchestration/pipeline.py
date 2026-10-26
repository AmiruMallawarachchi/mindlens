"""Full-turn pipeline wiring for the legacy orchestrator."""

from __future__ import annotations

from typing import Any

from app.agents.base_agent import AgentContext
from app.agents.groq_client import begin_degradation_tracking
from app.core.anonymizer import anonymize
from app.core.emotional_os import EmotionalOperatingState
from .generation import generate_response
from .memory import recall_and_apply_memory
from .retrieval import retrieve_context
from .result import build_pipeline_result
from .shared import StageCallback, _SILENT_AGENTS


class OrchestratorPipelineMixin:
    async def run_full_pipeline(
        self,
        user_text: str,
        *,
        user_name: str = "friend",
        session_history: list[dict] | None = None,
        rag_chunks: list[str] | None = None,
        user_id: str | None = None,
        memory: dict[str, Any] | None = None,
        on_stage: StageCallback | None = None,
    ) -> dict:
        """
        Complete turn pipeline:
        1. Run model inference → build EOS
        2. Recall relevant memory and merge into EOS
        3. Retrieve RAG context (if not provided)
        4. Select agents based on EOS
        5. Run all agents in parallel
        6. Assemble response
        7. Return full result with assembled text

        `on_stage`, when supplied, is awaited at each stage boundary with
        the stage's id and a short factual summary of what that stage just
        produced. It exists because this whole method runs to completion
        before the router streams anything, so the client previously received
        all four trail sections at once, already finished — there was no
        "one by one" to see. These callbacks fire as each stage genuinely
        completes, so the progression a user watches is the real one rather
        than a staggered animation over work that already ended.

        `memory` is the caller's already-fetched `user_memory` document (or
        None) — the orchestrator stays DB-free by design, so the router reads
        Mongo and hands the document in rather than this method doing its own
        lookup.
        """
        # Track LLM fallbacks for the whole turn, across every agent.
        degradation = begin_degradation_tracking()

        # Step 1: Model inference + EOS. The turn count comes from the history
        # the caller already loaded — without it, personality, progress and
        # checkin_scheduler sit permanently unselectable behind a 0.
        turn_result = await self.process_turn(
            user_text,
            user_id=user_id,
            session_turn_count=len(session_history or []),
        )
        eos = EmotionalOperatingState(**turn_result["eos"])
        agent_names = turn_result["agents"]
        crisis_flag = turn_result["crisis_flag"]

        if on_stage:
            safety = turn_result.get("safety") or {}
            await on_stage(
                "safety",
                "Crisis signals found — everything else pauses."
                if crisis_flag
                else "Both layers clear.",
            )
            await on_stage(
                "reading",
                f"Reading {eos.surface_emotion}"
                + (
                    f" at {eos.surface_confidence:.2f} confidence."
                    if eos.surface_confidence is not None
                    else "."
                ),
            )
            del safety

        recall = recall_and_apply_memory(
            memory,
            user_text=user_text,
            eos=eos,
            crisis_flag=crisis_flag,
        )

        if on_stage:
            await on_stage(
                "memory",
                f"Recalled {len(recall.memory_recalled)} thing"
                + ("" if len(recall.memory_recalled) == 1 else "s")
                + " from before."
                if recall.memory_recalled
                else "Nothing on file matched this turn.",
            )

        substantive, rag_chunks, rag_status = await retrieve_context(
            self._retriever,
            user_text,
            eos,
            crisis_flag=crisis_flag,
            rag_chunks=rag_chunks,
            on_stage=on_stage,
        )

        # Step 4: Build agent context
        #
        # History is anonymized the same way as the current turn — empathy_agent
        # and checkin_agent both fold the last few turns of `session_history`
        # into the Groq prompt verbatim (as recent-context, not just the current
        # message), so an email or phone number typed last turn was previously
        # sent to Groq unstripped this turn. Only `text` carries user-authored
        # content; role/timestamp/etc. pass through untouched.
        anonymized_history = [
            {**turn, "text": anonymize(turn.get("text", ""))} for turn in (session_history or [])
        ]
        ctx = AgentContext(
            eos=eos,
            user_text=anonymize(user_text),
            user_name=user_name,
            session_history=anonymized_history,
            rag_chunks=rag_chunks or [],
            # Local-only, never forwarded to Groq or RAG -- see
            # AgentContext.raw_user_text's docstring for why
            # session_memory_save specifically needs it.
            raw_user_text=user_text,
        )

        if on_stage:
            speaking = [a for a in agent_names if a not in _SILENT_AGENTS]
            await on_stage(
                "approach",
                "Working through it with " + ", ".join(speaking) + "."
                if speaking
                else "Staying with what you said.",
            )

        outputs, assembled_text, options_payload = await generate_response(
            agent_names=agent_names,
            crisis_flag=crisis_flag,
            ctx=ctx,
            assembler=self._assembler,
            user_name=user_name,
            user_text=user_text,
        )
        return build_pipeline_result(
            eos=eos,
            agent_names=agent_names,
            crisis_flag=crisis_flag,
            assembled_text=assembled_text,
            outputs=outputs,
            turn_result=turn_result,
            degradation=degradation,
            recall=recall,
            options_payload=options_payload,
            rag_status=rag_status,
            rag_chunks=rag_chunks,
            substantive=substantive,
        )
