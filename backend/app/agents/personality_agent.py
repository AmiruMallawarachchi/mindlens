"""
Personality Agent — MindLens v3 SYSTEM.md §5.14
===================================================
Background update after every session (not visible to user).
Uses NO LLM. Rule-based scoring only.

Purpose: Track introvert/extrovert score to personalise recommendations.
Score: 0.0 (introvert) to 1.0 (extrovert) — starts at 0.5.

Updates:
- +0.05 observed if user mentions social activity positively
- -0.05 observed if user prefers solo activities or mentions social drain
- Smoothed into the standing score with an EMA, then capped at [0.1, 0.9]

The EMA matters: without it a single message about a party would overwrite a
disposition built over weeks. At alpha=0.2 one turn moves the score by at most
0.01, so a genuine shift needs to be said repeatedly before it takes hold.

The score is read from and written back to `eos.introvert_score`, persisted at
`preferences.introvert_score` by the chat router. It is deliberately *not*
`eos.social_energy` — that field means how much social capacity the user has
right now, which is a different quantity that happens to share a scale.

Used by: Routine agent, Music agent, Challenge agent (tone calibration).
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent

# Keywords for detecting social/introvert/extrovert tendencies
SOCIAL_POSITIVE_KEYWORDS = [
    "hanging out", "met up with", "party", "group", "friends", "fun with",
    "social", "together", "went out with", "catch up", "celebration",
    "laughed with", "had a good time with", "crowd", "event", "gathering",
    "spoke to", "called", "chat with", "face to face", "in person",
]

SOLO_POSITIVE_KEYWORDS = [
    "alone", "by myself", "solo", "quiet", "peaceful", "my own space",
    "recharge alone", "me time", "reading", " Netflix ", "gaming alone",
    "peace and quiet", "no one around", "just me", "on my own",
]

SOCIAL_DRAIN_KEYWORDS = [
    "draining", "exhausted after social", "socially drained",
    "people are tiring", "too many people", "overwhelmed by crowd",
    "need to be alone after", "social anxiety", "avoided the party",
]

#: Weight given to this turn's observation. new = (1-a)*old + a*observed.
EMA_ALPHA = 0.2

#: The score never saturates — a profile must stay able to move back.
SCORE_FLOOR = 0.1
SCORE_CEILING = 0.9


class PersonalityAgent(BaseAgent):
    """
    Tracks introvert/extrovert score to personalise recommendations.
    RULE-BASED — never calls any LLM. Zero latency.

    Trigger: Background update after every session (not visible to user).
    Output: Score update (0.0 introvert to 1.0 extrovert).
    """

    def __init__(self) -> None:
        super().__init__(
            name="personality",
            description="Adapt tone and style based on user personality (rule-based, no LLM)",
            llm_tier="none",  # SYSTEM.md: "None (rule-based scoring)"
            max_tokens=0,     # No LLM generation
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """
        Update personality score based on user text.
        Returns the score update (not visible to user directly).
        """
        text_lower = ctx.user_text.lower()

        # Score delta
        delta = 0.0
        reasons: list[str] = []

        # Check for social positive indicators
        for kw in SOCIAL_POSITIVE_KEYWORDS:
            if kw in text_lower:
                delta += 0.05
                reasons.append(f"social_positive: '{kw}'")
                break  # One positive social mention per turn

        # Check for solo positive / social drain indicators
        for kw in SOLO_POSITIVE_KEYWORDS:
            if kw in text_lower:
                delta -= 0.05
                reasons.append(f"solo_preference: '{kw}'")
                break

        for kw in SOCIAL_DRAIN_KEYWORDS:
            if kw in text_lower:
                delta -= 0.05
                reasons.append(f"social_drain: '{kw}'")
                break

        # If no indicators detected, no change
        if abs(delta) < 0.01:
            return AgentOutput(
                agent_name=self.name,
                text="",
                metadata={
                    "skipped": True,
                    "reason": "no personality indicators detected",
                    "llm_tier": "none",
                    "introvert_score": ctx.eos.introvert_score,
                    "delta": 0.0,
                },
            )

        # This turn's raw observation, then smoothed into the standing score.
        # `delta` is what this message alone suggests; the EMA decides how much
        # of that a long-running profile should actually absorb.
        current_score = ctx.eos.introvert_score
        observed = current_score + delta
        smoothed = (1 - EMA_ALPHA) * current_score + EMA_ALPHA * observed
        new_score = max(SCORE_FLOOR, min(SCORE_CEILING, smoothed))

        # Store the score. The chat router persists this to
        # preferences.introvert_score — see _save_introvert_score there.
        score_update = {
            "introvert_score": new_score,
            "previous_score": current_score,
            "observed": observed,
            "delta": delta,
            "reasons": reasons,
        }

        return AgentOutput(
            agent_name=self.name,
            text="",  # Not visible to user
            metadata={
                "llm_tier": "none",
                "score_update": score_update,
                "introvert_score": new_score,
                "previous_score": current_score,
                "delta": delta,
                "reasons": reasons,
                "rule_based": True,
                "skipped": False,
            },
        )
