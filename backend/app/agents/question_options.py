"""
Structured follow-up options.

When a reply ends on a question, the model may offer two to four short
answers plus a free-text escape, rendered as buttons rather than prose.

This is deliberately *not* the canned menu that empathy_agent's rule 5
forbids. That bug was a fixed sentence — "music, breathing, journaling, or
just talking — what do you need?" — hardcoded into the prompt and recited
verbatim on every single turn, including to someone who had only said they
wanted help. The distinction that matters:

- these options are generated per turn from what was actually said, never a
  stock list;
- they are structured data validated against a schema, never text parsed
  back out of the reply, so a model that ignores the format produces no
  options rather than a mangled half-menu;
- they are offered only when the reply genuinely asks something.

Anything that fails validation returns None. Showing no options is always
acceptable; showing wrong ones is not.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.agents.groq_client import get_groq_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

MIN_OPTIONS = 2
MAX_OPTIONS = 4
MAX_OPTION_CHARS = 48

_PROMPT = (
    "You turn a counsellor's follow-up question into a few concrete answers "
    "the person could tap instead of typing.\n\n"
    "Return ONLY a JSON object: {\"options\": [\"...\", \"...\"]}\n"
    "Rules:\n"
    f"- Between {MIN_OPTIONS} and {MAX_OPTIONS} options.\n"
    f"- Each under {MAX_OPTION_CHARS} characters.\n"
    "- Write them in the person's voice, as answers they would give — not "
    "as things the app can do for them.\n"
    "- They must be genuinely different answers, not rewordings.\n"
    "- Never list app features (music, journaling, breathing). This is about "
    "what they might say next, not a menu of tools.\n"
    "- If the question has no small set of sensible answers, return "
    "{\"options\": []}. That is a good outcome, not a failure."
)


def _looks_like_a_question(reply: str) -> bool:
    """Cheap gate so most turns never make the extra call at all."""
    return reply.rstrip().endswith("?")


def _parse(raw: str) -> list[str] | None:
    """Pull the options array out, or give up.

    Models wrap JSON in prose or fences often enough that a bare
    json.loads is too brittle, but anything beyond "find the object" is
    guessing at intent — so this extracts one object and validates it
    strictly rather than trying to repair bad output.
    """
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None

    options = parsed.get("options")
    if not isinstance(options, list):
        return None

    cleaned: list[str] = []
    for item in options:
        if not isinstance(item, str):
            return None  # a non-string means the model ignored the shape
        text = " ".join(item.split())
        if not text or len(text) > MAX_OPTION_CHARS:
            return None
        cleaned.append(text)

    # Case-insensitive dedupe — two options that say the same thing are a
    # worse choice than no options.
    seen: set[str] = set()
    unique = [o for o in cleaned if not (o.lower() in seen or seen.add(o.lower()))]
    if len(unique) < MIN_OPTIONS or len(unique) > MAX_OPTIONS:
        return None
    return unique


async def build_options(reply_text: str, user_text: str) -> dict[str, Any] | None:
    """Return an options payload for this reply, or None."""
    if not reply_text or not _looks_like_a_question(reply_text):
        return None

    try:
        result = await get_groq_client().chat(
            system_prompt=_PROMPT,
            user_prompt=(
                f"They said: {user_text[:400]}\n"
                f"The reply asks: {reply_text[-400:]}"
            ),
            model_tier="8B",
            max_tokens=180,
            temperature=0.4,
        )
    except Exception as exc:
        logger.warning("Option generation failed: %s", exc)
        return None

    options = _parse(result.text or "")
    if not options:
        return None

    return {
        # The question itself is already the last line of the reply; repeating
        # it above the buttons would say the same thing twice.
        "options": options,
        # Never a closed set. The point is to save typing, not to constrain
        # what someone is allowed to say.
        "allow_other": True,
    }
