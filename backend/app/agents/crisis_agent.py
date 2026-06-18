"""
Crisis Agent — Emergency Response Handler

NEVER uses LLM. Zero hallucination risk.
Template-based responses with resource links.

This agent triggers when safety_gate detects crisis indicators.
It bypasses ALL other agents and responds with calibrated support + resources.
"""


from pydantic import BaseModel

from backend.app.core.emotional_os import EmotionalOperatingState

# --- Crisis Resource Templates ---

CRISIS_RESOURCES = {
    "GENERAL": {
        "Sri Lanka": {
            "NIMH": {"number": "1926", "description": "National Mental Health Institute - 24/7"},
            "Sumithrayo": {
                "number": "+94 11 2696666",
                "description": "Crisis support line - free",
            },
            "Befrienders": {
                "number": "+94 11 2328729",
                "description": "Emotional support - confidential",
            },
        },
        "International": {
            "US_988": {"number": "988", "description": "Suicide & Crisis Lifeline - US"},
            "UK_116": {
                "number": "116 123",
                "description": "Samaritans - UK",
            },
            "International_ICall": {
                "url": "https://www.icall.org.in",
                "description": "iCall - India & regional",
            },
        },
    }
}

# --- Crisis Response Templates ---

CRISIS_TEMPLATES = {
    "IMMEDIATE": """
I can see you're in a really difficult moment right now, {name}.
What you're feeling matters deeply, and so do you.

I'm here with you, but I also want to connect you with people who are trained for this exact situation:

📞 {resource1_name}: {resource1_phone}
📞 {resource2_name}: {resource2_phone}

These are real people, available right now, and they're trained for crisis support.

Can you reach out to one of them right now? You don't have to go through this alone.
I'll be right here when you're ready to talk more.
""",
    "FOLLOWUP": """
Thank you for talking to me about this, {name}.
I want to make sure you're safe.

Have you been able to reach out to any of the resources I mentioned?
Or would it help if I walked you through how to contact them?

Remember:
✓ You deserve support
✓ This moment doesn't define your future
✓ People care about you (even if it doesn't feel that way right now)

What would help you most right now?
""",
    "GROUNDING": """
Let's take a moment together, {name}.

I want to help you feel a bit more grounded right now:

1. Look around and name 5 things you can see
2. Notice 4 things you can touch
3. Listen for 3 sounds you can hear
4. Think of 2 scents (real or remembered)
5. Name 1 taste

This is the 5-4-3-2-1 grounding technique. It helps bring you back to the present moment.

Take your time. I'm here.
""",
}


class CrisisResponse(BaseModel):
    """Structured crisis response."""

    is_crisis: bool
    message: str
    resources: list[dict]
    severity: str  # "high" or "extreme"
    recommend_call_emergency: bool


class CrisisAgent:
    """
    Crisis intervention agent.

    Runs ONLY when safety_gate triggers.
    Template-based, zero LLM inference.
    """

    def __init__(self):
        self.name = "crisis_agent"
        self.uses_llm = False

    async def handle_crisis(
        self,
        user_message: str,
        eos: EmotionalOperatingState,
        user_name: str = "friend",
        user_nickname: str | None = None
    ) -> CrisisResponse:
        """
        Generate crisis response.

        Args:
            user_message: User's current message
            eos: Emotional Operating System state
            user_name: User's full name
            user_nickname: User's preferred nickname

        Returns:
            CrisisResponse with message + resources
        """
        display_name = user_nickname or user_name.split()[0]

        # Determine severity
        severity = "extreme" if eos.distress_level >= 0.95 else "high"
        recommend_emergency_call = eos.distress_level >= 0.95

        # Select template
        if "ground" in user_message.lower() or "earth" in user_message.lower():
            template = CRISIS_TEMPLATES["GROUNDING"]
        elif "already" in user_message.lower() and "call" in user_message.lower():
            template = CRISIS_TEMPLATES["FOLLOWUP"]
        else:
            template = CRISIS_TEMPLATES["IMMEDIATE"]

        # Get resources for region (hardcoded to Sri Lanka + International for now)
        resources = self._build_resource_list()

        # Format message
        message = template.format(
            name=display_name,
            resource1_name=resources[0]["name"],
            resource1_phone=resources[0]["phone"],
            resource2_name=resources[1]["name"],
            resource2_phone=resources[1]["phone"],
        )

        return CrisisResponse(
            is_crisis=True,
            message=message,
            resources=resources,
            severity=severity,
            recommend_call_emergency=recommend_emergency_call,
        )

    def _build_resource_list(self) -> list[dict]:
        """Build localized resource list."""
        resources = []

        # Sri Lanka resources (primary)
        nimh = CRISIS_RESOURCES["GENERAL"]["Sri Lanka"]["NIMH"]
        resources.append({
            "name": "NIMH Sri Lanka",
            "phone": nimh["number"],
            "description": nimh["description"],
            "region": "Sri Lanka",
            "priority": 1,
        })

        sumithrayo = CRISIS_RESOURCES["GENERAL"]["Sri Lanka"]["Sumithrayo"]
        resources.append({
            "name": "Sumithrayo",
            "phone": sumithrayo["number"],
            "description": sumithrayo["description"],
            "region": "Sri Lanka",
            "priority": 1,
        })

        befrienders = CRISIS_RESOURCES["GENERAL"]["Sri Lanka"]["Befrienders"]
        resources.append({
            "name": "Befrienders",
            "phone": befrienders["number"],
            "description": befrienders["description"],
            "region": "Sri Lanka",
            "priority": 2,
        })

        # International resources (secondary)
        us_988 = CRISIS_RESOURCES["GENERAL"]["International"]["US_988"]
        resources.append({
            "name": "US Suicide & Crisis Lifeline",
            "phone": us_988["number"],
            "description": us_988["description"],
            "region": "USA",
            "priority": 2,
        })

        return resources

    def get_crisis_warning_signs(self) -> list[str]:
        """
        Return the crisis warning signs this agent looks for.

        For transparency to users.
        """
        return [
            "Suicidal ideation or intent",
            "Self-harm or plans to self-harm",
            "Severe emotional dysregulation",
            "Acute distress (9+/10)",
            "Feeling hopeless/no future",
            "Acute loss (death, breakup, job)",
            "Substance use crisis",
            "Violence or intent to harm others",
        ]


# --- Singleton instance ---
crisis_agent = CrisisAgent()
