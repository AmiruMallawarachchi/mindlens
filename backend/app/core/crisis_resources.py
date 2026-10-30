"""Crisis contact rows returned to the UI.

These are data, not model output. The crisis path never calls Groq, and the
client renders this list as contact rows beside the template response.
"""

from __future__ import annotations

CRISIS_RESOURCES: list[dict[str, str]] = [
    {"name": "Sri Lanka - Sumithrayo", "number": "011 269 6666"},
    {"name": "National Mental Health Helpline", "number": "1926"},
    {"name": "Emergency services", "number": "119 / 110"},
]
