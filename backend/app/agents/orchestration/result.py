"""Result payload construction for the legacy orchestrator pipeline."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.core.emotional_os import EmotionalOperatingState
from .shared import MODALITY_DRIVEN_AGENTS


def build_pipeline_result(
    *,
    eos: EmotionalOperatingState,
    agent_names: list[str],
    crisis_flag: bool,
    assembled_text: str,
    outputs: list[Any],
    turn_result: dict[str, Any],
    degradation: set[str],
    recall: Any,
    options_payload: Any,
    rag_status: str,
    rag_chunks: list[str] | None,
    substantive: bool,
) -> dict[str, Any]:
    return {
                # mode="json": eos carries PeopleGraph.mentioned_at and other
                # datetime fields that don't survive a plain model_dump() into
                # the WebSocket send_json() call downstream — see
                # EmotionalOperatingState.to_dict()'s docstring.
                "eos": eos.model_dump(mode="json"),
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
                # SYSTEM.md §13.3: "Memory recalled" in the thinking panel. Empty
                # unless something on file was genuinely relevant to this turn.
                "memory_recalled": recall.memory_recalled,
                "options": options_payload,
                # Everything the reasoning trail needs to describe this turn
                # truthfully, rather than inferring it or reciting a fixed
                # sentence. See connection_manager.send_thinking_update.
                "telemetry": {
                    "rag": {
                        "status": rag_status,
                        "chunks": len(rag_chunks or []),
                        # Named only when the reranker was actually configured to
                        # run for this turn -- a degraded reranker call is already
                        # reported separately (the "rag:reranker" degradation),
                        # so this is a statement of what was asked to run, not a
                        # guarantee every chunk got its score from it.
                        "model": (
                            settings.rag_reranker_model_id.split("/")[-1]
                            if rag_status == "ran" and settings.rag_reranker_enabled
                            else None
                        ),
                    },
                    # Only claim a modality when one actually shaped a running
                    # agent. Every turn carries a modality field, but on a turn
                    # where no modality-driven agent ran, naming one describes a
                    # decision that had no effect.
                    "modality": (
                        eos.modality.value
                        if any(a in agent_names for a in MODALITY_DRIVEN_AGENTS)
                        else None
                    ),
                    "substantive": substantive,
                },
            }
