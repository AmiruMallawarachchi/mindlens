"""Conditional hosted retrieval and truthful retrieval-stage summaries."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.anonymizer import anonymize
from app.core.emotional_os import EmotionalOperatingState
from app.utils.logger import get_logger
from .shared import StageCallback, turn_is_substantive

logger = get_logger("app.agents.orchestrator")


async def retrieve_context(
    retriever: Any,
    user_text: str,
    eos: EmotionalOperatingState,
    *,
    crisis_flag: bool,
    rag_chunks: list[str] | None,
    on_stage: StageCallback | None,
) -> tuple[bool, list[str] | None, str]:
    # Step 3: Retrieve RAG context if not provided.
    #
    # rag_status is reported to the client, so "skipped" is a fact the UI
    # can state rather than something it has to guess at or stay silent
    # about. Retrieval used to run on every non-crisis turn, including
    # "hi".
    substantive = turn_is_substantive(user_text, eos.distress_level)
    rag_status = "provided"
    if crisis_flag:
        # Crisis: skip RAG, use crisis protocols directly
        rag_chunks = []
        rag_status = "skipped_crisis"
    elif not substantive:
        rag_chunks = []
        rag_status = "skipped_trivial"
    elif rag_chunks is None:
        try:
            rag_chunks = await asyncio.to_thread(
                retriever.retrieve, anonymize(user_text), eos
            )
            rag_status = "ran"
        except Exception as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            rag_chunks = []
            rag_status = "failed"

    if on_stage:
        await on_stage(
            "retrieval",
            f"Pulled {len(rag_chunks or [])} passage"
            + ("" if len(rag_chunks or []) == 1 else "s")
            + " from the therapy notes."
            if rag_status == "ran" and rag_chunks
            else "Searched and found nothing close enough."
            if rag_status == "ran"
            else "No lookup needed for this one."
            if rag_status == "skipped_trivial"
            else "Skipped — safety comes first."
            if rag_status == "skipped_crisis"
            else "Couldn't reach the therapy notes.",
        )
    return substantive, rag_chunks, rag_status
