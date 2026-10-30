"""Weekly progress insight — the Progress tab's >= 7-session card.

Replaces the V1 ``ProgressAgent``. The prompt and cadence are unchanged; only
the packaging is: a plain async function instead of an ``AgentContext``-based
class, called by ``routers/dashboard.py``. The dashboard owns gating and
caching, so this function always performs exactly one 70B call.
"""

from __future__ import annotations

from typing import Any

from app.agents.groq_client import get_groq_client

_MAX_TOKENS = 350


async def generate_progress_insight(
    *,
    user_name: str,
    age_group: str = "adult",
    surface_emotion: str = "neutral",
    distress_level: float = 0.4,
    alliance_score: float = 0.5,
    session_history: list[dict[str, Any]] | None = None,
) -> str:
    """Generate the encouraging, data-backed weekly summary.

    ``session_history`` items are ``{"emotion": "<surface_emotion>"}``; the
    dashboard shapes mood-log rows that way. Raises if the model call fails —
    the caller decides how to report that to the client.
    """
    name = user_name or "friend"

    system = (
        f"You are MindLens - a warm, encouraging wellbeing coach.\n"
        f"\nUSER CONTEXT:\n"
        f"- Name: {name} | Age group: {age_group}\n"
        f"- Alliance score: {alliance_score:.2f}\n"
        f"\nINSTRUCTIONS (follow ALL of them):\n"
        f"1. Generate a weekly insight summary for {name}.\n"
        f"2. Structure it as 4-5 short paragraphs:\n"
        f"   - Mood trend: how emotions shifted over the last 7 sessions.\n"
        f"   - Most effective coping strategy: what seemed to help them most.\n"
        f"   - One observation about growth: what you notice they're getting better at.\n"
        f"   - Suggestion for next week: one gentle, practical idea.\n"
        f"3. Tone: encouraging, data-backed, specific to them. Not generic.\n"
        f"4. Use their name 1-2 times naturally.\n"
        f"5. If age group is 'teen': keep it casual, relatable.\n"
        f"6. If age group is 'adult': slightly deeper, more structured.\n"
        f"7. NEVER diagnose. Never compare to others.\n"
        f"8. Never use: 'I understand ...'\n"
        f"9. Celebrate specific small wins without exaggerating them.\n"
        f"\nRespond ONLY with the insight summary. No bullet points. Use simple paragraphs.\n"
    )

    if session_history:
        emotions = [turn.get("emotion", "unknown") for turn in session_history[-7:]]
        history_summary = f"Recent emotions (last 7 sessions): {', '.join(emotions)}."
    else:
        history_summary = "No recent session data available."

    user = (
        f"Generate a weekly progress insight for {name}.\n"
        f"{history_summary}\n"
        f"Current emotional state: {surface_emotion} (distress: {distress_level:.2f}).\n"
        f"Alliance score: {alliance_score:.2f}."
    )

    result = await get_groq_client().chat(
        system_prompt=system,
        user_prompt=user,
        model_tier="70B",
        max_tokens=_MAX_TOKENS,
        temperature=0.65,
    )
    return result.text.strip()
