"""
Distortion Agent — MindLens v3 SYSTEM.md §5.7
================================================
Trigger: modality == "CBT"
LLM: None (uses fine-tuned RoBERTa distortion model).

Purpose: Identify cognitive distortions using the trained model.
Output: { distortion_label: str, confidence: float, explanation: str }
10 classes: catastrophizing, mind_reading, all_or_nothing, personalization,
            overgeneralization, emotional_reasoning, should_statements,
            jumping_to_conclusions, magnification, mental_filter

Used by: Challenge agent (what to challenge), UI badge (shows user their pattern).

The shared model registry populates the EOS distortion label before this agent
runs. A deterministic keyword heuristic is retained as a degraded fallback.
"""

from __future__ import annotations

import random

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent

# 10 distortion classes (SYSTEM.md §5.7)
DISTORTION_LABELS = [
    "catastrophizing",
    "mind_reading",
    "all_or_nothing",
    "personalization",
    "overgeneralization",
    "emotional_reasoning",
    "should_statements",
    "jumping_to_conclusions",
    "magnification",
    "mental_filter",
]

# Keyword-based fallback detection (heuristic, until model is trained)
DISTORTION_KEYWORDS = {
    "catastrophizing": ["everything is ruined", "my life is over", "it will never", "always terrible", "disaster", "worst", "can't recover"],
    "mind_reading": ["they think", "they must think", "they probably think", "everyone thinks", "people see me as"],
    "all_or_nothing": ["always", "never", "completely", "totally", "everyone", "nobody", "either or", "perfect"],
    "personalization": ["my fault", "because of me", "i caused", "i made them", "they're mad at me"],
    "overgeneralization": ["always happens", "every time", "never works", "always fail", "everyone does"],
    "emotional_reasoning": ["i feel like", "it feels like", "i feel so", "because i feel"],
    "should_statements": ["should have", "shouldn't have", "must have", "need to", "supposed to", "have to"],
    "jumping_to_conclusions": ["they must be", "probably means", "obviously", "clearly they", "i know they"],
    "magnification": ["huge", "massive", "catastrophic", "the worst", "completely destroyed", "everything is ruined"],
    "mental_filter": ["only thing i see", "all i can think", "only bad part", "nothing good", "only negative"],
}


# Several phrasings per pattern so the same observation doesn't arrive in
# identical words every time it applies. All hedged ("might", "seems") on
# purpose: this comes from the weakest model in the set (0.17 macro-F1 over
# ten classes), so a flat assertion about how someone is thinking would
# overstate a near-chance read.
EXPLANATIONS: dict[str, list[str]] = {
    "catastrophizing": [
        "It sounds like you might be imagining the worst possible outcome. What if things don't turn out as badly as you fear?",
        "There's a jump to the worst case in that. What's the most likely version, rather than the worst one?",
        "That reads like the bad ending arriving before the story's finished. What else could happen instead?",
    ],
    "mind_reading": [
        "It seems like you might be assuming what others are thinking. What if they don't see things the way you imagine?",
        "You sound quite certain about what's going on in their head. What do you actually know for sure?",
        "That's a guess at someone else's thoughts, held pretty firmly. What would asking them look like?",
    ],
    "all_or_nothing": [
        "It looks like you might be seeing things in extremes. What about the middle ground?",
        "That's framed as all or nothing. Is there a version somewhere between the two?",
        "There's no in-between in how that's phrased. Where would a partly-true sit?",
    ],
    "personalization": [
        "It seems like you might be taking responsibility for things outside your control. What if it's not all on you?",
        "You've put yourself at the centre of that. How much of it was actually yours to decide?",
        "That reads as though it's all your doing. What part genuinely wasn't?",
    ],
    "overgeneralization": [
        "It sounds like you might be drawing a big conclusion from one experience. What if this time is different?",
        "One instance is carrying a lot of weight there. Has it always gone that way?",
        "That turns a single time into a rule. What are the exceptions?",
    ],
    "emotional_reasoning": [
        "It seems like you're treating your feelings as facts. What if your feeling is just one perspective?",
        "The feeling is real, but it isn't the same thing as evidence. What would the evidence say on its own?",
        "You feel it strongly, so it reads as true. What would you notice if the feeling were quieter?",
        "That's your feeling reporting on the situation. What would someone outside it see?",
    ],
    "should_statements": [
        "It looks like you might be using 'should' on yourself. What would you say to a friend in the same situation?",
        "There's a rule in there you're holding yourself to. Where did it come from?",
        "That's a lot of 'should'. What would 'could' sound like instead?",
    ],
    "jumping_to_conclusions": [
        "It sounds like you might be reaching a conclusion without all the facts. What if there's another explanation?",
        "That lands on an answer quickly. What else would fit what you actually know?",
        "There's a gap between what happened and what it means there. What could fill it differently?",
    ],
    "magnification": [
        "It seems like you might be making this feel bigger than it is. What if you looked at just one small piece?",
        "That's grown quite large in the telling. What's its actual size?",
        "It's filling the whole frame right now. What would it look like scaled down?",
    ],
    "mental_filter": [
        "It looks like you might be focusing only on the negative parts. What about the other side of the situation?",
        "The difficult part is doing all the talking there. What else was in it?",
        "That keeps returning to one detail. What's around it?",
    ],
    "none": [
        "No clear thinking pattern detected. That's okay — sometimes feelings are just feelings.",
    ],
}

class DistortionAgent(BaseAgent):
    """
    Identifies cognitive distortions using a fine-tuned model.

    Trigger: modality == CBT.
    """

    def __init__(self) -> None:
        super().__init__(
            name="distortion",
            description="Identify cognitive distortions using fine-tuned model",
            llm_tier="none",  # Will use model, not LLM
            max_tokens=0,
            always_runs=False,
        )
        # Placeholder for the fine-tuned model (loaded from HF Hub after training)
        self._model = None  # type: ignore

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """
        Detect cognitive distortion in user text.
        Returns: { distortion_label, confidence, explanation }
        """
        # Skip if not CBT modality
        if ctx.eos.modality.value != "CBT":
            return AgentOutput(
                agent_name=self.name,
                text="",
                metadata={
                    "skipped": True,
                    "reason": f"modality_not_cbt ({ctx.eos.modality.value})",
                    "llm_tier": "none",
                },
            )

        label = ctx.eos.distortion_label
        model_used = "distortion_classifier"
        # The classifier's real score, not a placeholder. This used to be a
        # flat 0.5 whenever any label existed, which put a fabricated number
        # into the turn's metadata and the admin panel.
        confidence = ctx.eos.distortion_score if label else 0.0
        if not label:
            label, confidence = self._keyword_detect(ctx.user_text)
            model_used = "keyword_fallback"
        explanation = self._build_explanation(label, ctx.user_text)

        return AgentOutput(
            agent_name=self.name,
            text=explanation,
            metadata={
                "distortion_label": label,
                "confidence": confidence,
                "llm_tier": "none",
                "model_used": model_used,
            },
        )

    def _keyword_detect(self, text: str) -> tuple[str, float]:
        """Keyword-based heuristic detection (fallback)."""
        text_lower = text.lower()
        best_label = "none"
        best_score = 0.0

        for label, keywords in DISTORTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_label = label

        # Normalize score to confidence (0-1)
        confidence = min(best_score * 0.3, 0.95)
        return best_label, confidence

    def _build_explanation(self, label: str, text: str) -> str:
        """Build a gentle explanation of the detected distortion.

        Several phrasings per pattern, chosen at random. There used to be
        exactly one sentence per label, so a user whose turns kept landing on
        the same pattern read the identical sentence — "It seems like you're
        treating your feelings as facts. What if your feeling is just one
        perspective?" — reply after reply after reply. The observation may be
        sound each time; saying it in the same seventeen words is what makes
        it stop landing as noticing and start landing as a tic.
        """
        return random.choice(EXPLANATIONS.get(label, EXPLANATIONS["none"]))
