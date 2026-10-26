"""Run selected agents and assemble the user-facing response."""

from __future__ import annotations

import asyncio
from typing import Any

from app.agents.base_agent import AgentContext, AgentOutput, get_registry
from app.agents.question_options import build_options
from app.agents.response_assembler import ResponseAssembler
from app.utils.logger import get_logger

logger = get_logger("app.agents.orchestrator")


async def generate_response(
    *,
    agent_names: list[str],
    crisis_flag: bool,
    ctx: AgentContext,
    assembler: ResponseAssembler,
    user_name: str,
    user_text: str,
) -> tuple[list[AgentOutput], str, Any]:
    # Step 5: Run agents in parallel
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

    # Step 6: Assemble response
    assembled_text = assembler.assemble(
        outputs,
        in_crisis=crisis_flag,
        user_name=user_name,
    )

    # Offered only when the reply actually asks something, and only
    # outside crisis â€” a crisis turn is templated and must not sprout
    # buttons (rule 3).
    options_payload = None
    if not crisis_flag:
        options_payload = await build_options(assembled_text, user_text)

    return outputs, assembled_text, options_payload

