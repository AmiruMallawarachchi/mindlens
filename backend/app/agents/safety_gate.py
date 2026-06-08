"""
3-Layer Safety Gate
CRITICAL: If ANY layer says crisis, we go to crisis mode. No overrides.
"""

from __future__ import annotations

import re
from typing import Dict, Any

from app.models.loader import model_manager

# Layer 1: Regex keywords (fast, synchronous, <1ms)
CRISIS_PATTERNS = [
    r"\b(kill myself|end my life|suicide|want to die)\b",
    r"\b(cut myself|self.?harm|overdose|jump off)\b",
    r"\b(can't go on|no reason to live|goodbye forever)\b",
    r"\b(going to end it|ending everything|not worth living)\b",
    r"\b(hurt myself|slit my wrist|hang myself)\b"
]


def layer1_keyword_scan(text: str) -> Dict[str, Any]:
    text_lower = text.lower()
    matched = [p for p in CRISIS_PATTERNS if re.search(p, text_lower)]
    return {
        "triggered": len(matched) > 0,
        "matches": matched,
        "layer": 1
    }


async def layer2_model_scan(text: str) -> Dict[str, Any]:
    """Your fine-tuned model from HuggingFace"""
    result = await model_manager.predict_crisis(text)
    res = result[0] if result else {}
    label = str(res.get("label", "NON_CRISIS")).upper()
    score = float(res.get("score", 0.0))
    is_crisis = label == "CRISIS" and score > 0.45
    return {
        "triggered": is_crisis,
        "probability": score,
        "severity": score,
        "layer": 2
    }


async def safety_gate(text: str) -> Dict[str, Any]:
    """
    Unbypassable safety gate.
    FAIL-SAFE: If Layer 1 OR Layer 2 says crisis → CRISIS MODE.
    """
    l1 = layer1_keyword_scan(text)
    l2 = await layer2_model_scan(text)
    
    is_crisis = l1["triggered"] or l2["triggered"]
    
    if is_crisis:
        severity = max(
            0.9 if l1["triggered"] else 0.0,
            l2.get("probability", 0.0)
        )
        
        return {
            "safe": False,
            "crisis_type": "suicidal_ideation" if severity > 0.7 else "crisis_state",
            "severity_score": severity,
            "layers_triggered": ([1] if l1["triggered"] else []) + ([2] if l2["triggered"] else []),
            "resources": [
                {"name": "NIMH Sri Lanka", "number": "1926", "available": "24/7"},
                {"name": "Sumithrayo", "number": "+94 11 2696666", "available": "24/7"},
                {"name": "988 Lifeline", "number": "988", "available": "24/7"},
                {"name": "Emergency (LK)", "number": "119", "available": "24/7"}
            ],
            "message": "I'm really concerned about what you've shared. You're not alone, and there are people who want to help right now."
        }
    
    return {"safe": True}

# Crisis templates (ZERO LLM - as per your proposal)
CRISIS_TEMPLATES = {
    "moderate": "I can hear how much pain you're in right now. Please reach out to NIMH at 1926 — they're available 24/7 and this is exactly what they're there for.",
    "severe": "What you're describing sounds incredibly serious. Your safety matters more than anything right now. Please call NIMH Sri Lanka immediately at 1926, or dial 119 for emergency services. You don't have to go through this alone."
}