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

NOTE: Until the model is trained (scripts/train_distortion_model.py),
      this agent falls back to Groq-based detection. After training,
      swap to the fine-tuned model for inference.
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

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


class DistortionAgent(BaseAgent):
    """
    Identifies cognitive distortions using a fine-tuned model.

    TEMPORARY: Uses keyword-based fallback + Groq LLM fallback until
    the fine-tuned model is trained and published to HF Hub.

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

        # Try fine-tuned model first (if loaded)
        if self._model is not None:
            # TODO: Add model inference once training is complete
            # This will be wired after scripts/train_distortion_model.py is run
            pass

        # Fallback: keyword-based heuristic + Groq LLM
        label, confidence = self._keyword_detect(ctx.user_text)

        # If confidence is too low, use Groq LLM for richer detection
        if confidence < 0.4:
            llm_result = await self._llm_fallback(ctx)
            if llm_result:
                label, confidence, explanation = llm_result
            else:
                explanation = "No clear distortion detected."
        else:
            explanation = self._build_explanation(label, ctx.user_text)

        return AgentOutput(
            agent_name=self.name,
            text=explanation,
            metadata={
                "distortion_label": label,
                "confidence": confidence,
                "llm_tier": "8B" if confidence < 0.4 else "none",
                "model_used": "keyword_fallback" if confidence >= 0.4 else "llm_fallback",
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
        """Build a gentle explanation of the detected distortion."""
        explanations = {
            "catastrophizing": "It sounds like you might be imagining the worst possible outcome. What if things don't turn out as badly as you fear?",
            "mind_reading": "It seems like you might be assuming what others are thinking. What if they don't see things the way you imagine?",
            "all_or_nothing": "It looks like you might be seeing things in extremes. What about the middle ground?",
            "personalization": "It seems like you might be taking responsibility for things outside your control. What if it's not all on you?",
            "overgeneralization": "It sounds like you might be drawing a big conclusion from one experience. What if this time is different?",
            "emotional_reasoning": "It seems like you're treating your feelings as facts. What if your feeling is just one perspective?",
            "should_statements": "It looks like you might be using 'should' on yourself. What would you say to a friend in the same situation?",
            "jumping_to_conclusions": "It sounds like you might be reaching a conclusion without all the facts. What if there's another explanation?",
            "magnification": "It seems like you might be making this feel bigger than it is. What if you looked at just one small piece?",
            "mental_filter": "It looks like you might be focusing only on the negative parts. What about the other side of the situation?",
            "none": "No clear thinking pattern detected. That's okay — sometimes feelings are just feelings.",
        }
        return explanations.get(label, explanations["none"])

    async def _llm_fallback(self, ctx: AgentContext) -> tuple[str, float, str] | None:
        """Groq LLM fallback for richer detection when keyword confidence is low."""
        try:
            client = get_groq_client()
            system = (
                f"You are a cognitive distortion detection expert.\n"
                f"Analyze the user's message and identify any cognitive distortion.\n"
                f"Available distortions: {', '.join(DISTORTION_LABELS)}\n"
                f"If none fit, return 'none'.\n"
                f"\nRespond ONLY in this exact format:\n"
                f"LABEL: <distortion_name>\n"
                f"CONFIDENCE: <0.0-1.0>\n"
                f"EXPLANATION: <one gentle sentence explaining the distortion>\n"
            )
            user = f"User said: {ctx.user_text}"

            result = await client.chat(
                system_prompt=system,
                user_prompt=user,
                model_tier="8B",
                max_tokens=150,
                temperature=0.6,
            )

            # Parse the response
            lines = result.text.strip().split("\n")
            label = "none"
            confidence = 0.0
            explanation = "No clear distortion detected."

            for line in lines:
                if line.startswith("LABEL:"):
                    label = line.replace("LABEL:", "").strip()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(line.replace("CONFIDENCE:", "").strip())
                    except ValueError:
                        confidence = 0.0
                elif line.startswith("EXPLANATION:"):
                    explanation = line.replace("EXPLANATION:", "").strip()

            # Validate label
            if label not in DISTORTION_LABELS and label != "none":
                label = "none"
                confidence = 0.0

            return label, confidence, explanation

        except Exception as exc:
            logger.warning("Distortion LLM fallback failed: %s", exc)
            return None
