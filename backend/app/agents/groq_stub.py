"""Development fallback response templates for local/stub mode."""

from collections.abc import Callable

from app.agents.groq_types import GroqResponse


def build_stub_response(
    system_prompt: str,
    user_prompt: str,
    model_tier: str,
    max_tokens: int,
    record_degradation: Callable[[str], None],
) -> GroqResponse:
    """Build the development response from the prompt's agent context."""
    record_degradation("stub")
    # Detect agent type from system prompt
    agent_name = "agent"
    if "empathy" in system_prompt.lower():
        agent_name = "empathy"
    elif "mindfulness" in system_prompt.lower():
        agent_name = "mindfulness"
    elif "crisis" in system_prompt.lower():
        agent_name = "crisis"
    elif "reflection" in system_prompt.lower():
        agent_name = "reflection"
    elif "challenge" in system_prompt.lower():
        agent_name = "challenge"
    elif "distortion" in system_prompt.lower():
        agent_name = "distortion"
    elif "routine" in system_prompt.lower():
        agent_name = "routine"
    elif "journaling" in system_prompt.lower():
        agent_name = "journaling"
    elif "check-in" in system_prompt.lower() or "checkin" in system_prompt.lower():
        agent_name = "checkin"
    elif "progress" in system_prompt.lower():
        agent_name = "progress"
    elif "personality" in system_prompt.lower():
        agent_name = "personality"

    # Template stubs keyed by agent name
    stubs: dict[str, str] = {
        "empathy": (
            "I hear you, {name}. It sounds like you're carrying a lot right now. "
            "You're not alone in this."
        ),
        "mindfulness": (
            "Let's take a breath together, {name}. Close your eyes if you want. "
            "Breathe in slowly for 4 countsâ€¦ hold for 4â€¦ out for 6. "
            "You're safe right here."
        ),
        "crisis": (
            "I can hear how much pain you're in. Please reach out to NIMH at 1926 â€” "
            "they're available 24/7. Your safety matters most."
        ),
        "reflection": (
            "It sounds like the core feeling here is {emotion}. "
            "What do you think is underneath that for you, {name}?"
        ),
        "challenge": (
            "That's a really strong thought, {name}. What evidence do you have "
            "that it's completely true?"
        ),
        "distortion": (
            "I notice a possible thinking pattern here. When you say that, "
            "what's the actual thought running through your mind?"
        ),
        "routine": (
            "A small routine might help anchor you, {name}. "
            "What if we tried one tiny thing at the same time tomorrow?"
        ),
        "journaling": (
            "Three questions for you, {name}:\n"
            "1. What emotion showed up most strongly today?\n"
            "2. What moment felt the hardest?\n"
            "3. What one small thing went okay?"
        ),
        "checkin": (
            "Hey {name}, just checking in. How are you feeling today? "
            "No pressure â€” just a gentle pause."
        ),
        "progress": (
            "Looking at your journey so far, {name}, you've been showing up consistently. "
            "That matters. What's one small win you noticed this week?"
        ),
        "personality": (
            "[Personality tone adapted for {name}.]"
        ),
    }

    # Extract user name from system prompt if available
    name = "friend"
    if "User's name:" in system_prompt:
        try:
            name_line = [line for line in system_prompt.split("\n") if "User's name:" in line][0]
            name = name_line.split(":")[-1].strip()
        except IndexError:
            pass

    # Extract emotion if available
    emotion = "sadness"
    if "surface_emotion" in system_prompt:
        try:
            emotion_line = [line for line in system_prompt.split("\n") if "surface_emotion" in line][0]
            emotion = emotion_line.split(":")[-1].strip().split()[0]
        except IndexError:
            pass

    template = stubs.get(agent_name, "I'm here with you, {name}.")
    text = template.format(name=name, emotion=emotion)

    # Truncate to max_tokens approximation (roughly 4 chars per token)
    max_chars = max_tokens * 4
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "â€¦"

    return GroqResponse(
        text=text,
        model_used=f"stub-{model_tier}",
        tokens_used=len(text.split()),
        latency_ms=0.0,
        finish_reason="stub",
    )

