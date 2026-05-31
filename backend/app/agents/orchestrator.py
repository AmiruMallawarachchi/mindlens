"""
Orchestrator: Runs all models in parallel, builds EmotionalOperatingState
"""

import asyncio
from typing import Dict, Optional
from app.models.loader import model_manager
from app.core.emotional_os import EmotionalOperatingState, InterventionReceptiveness

async def run_inference(text: str) -> Dict:
    """Run all models in parallel"""
    emotion_task = model_manager.predict_emotion(text)
    crisis_task = model_manager.predict_crisis(text)
    mh_task = model_manager.predict_mh(text)
    
    emotion, crisis, mh = await asyncio.gather(emotion_task, crisis_task, mh_task)
    
    return {
        "emotion": emotion,
        "crisis": crisis,
        "mh": mh
    }

def build_eos(
    inference_results: Dict,
    user_history: Optional[Dict] = None  # FIXED: Optional[Dict]
) -> EmotionalOperatingState:
    """Build EmotionalOperatingState from model outputs"""
    emotion = inference_results.get("emotion", {})
    crisis = inference_results.get("crisis", {})
    mh = inference_results.get("mh", {})
    
    # Distress calculation
    severity = emotion.get("severity", 0.5)
    mh_max = max(mh.get("conditions", {}).values()) if mh.get("conditions") else 0.0
    crisis_prob = crisis.get("probability", 0.0)
    
    distress = min(1.0, severity * 0.4 + mh_max * 0.25 + crisis_prob * 0.35)
    stability = max(0.0, 1.0 - distress - emotion.get("mental_fatigue", 0.3))
    
    # Trust level
    session_count = user_history.get("session_count", 0) if user_history else 0
    trust = min(1.0, 0.3 + (session_count * 0.05))
    
    # Receptiveness
    receptiveness = InterventionReceptiveness(
        music=0.9 if distress > 0.4 else 0.5,
        journaling=0.3 if stability < 0.3 else 0.7,
        challenge=max(0.0, (trust - 0.6) * stability * (1 - distress)),
        grounding=0.8 if distress > 0.6 else 0.4,
        breathing=0.9 if emotion.get("core_emotion") in ["anxiety", "fear"] else 0.3,
        routine=0.6 if "burnout" in str(mh.get("multi_label", [])) else 0.3,
        social_support=0.4 if emotion.get("attachment_style") == "avoidant" else 0.7
    )
    
    # Routing flags
    run_distortion = False
    run_challenge = trust > 0.6 and stability > 0.5 and distress < 0.6 and receptiveness.challenge > 0.3
    run_music = distress > 0.4 or emotion.get("mental_fatigue", 0) > 0.7
    run_mindfulness = emotion.get("core_emotion") in ["anxiety", "fear", "anger"] or distress > 0.5
    run_routine = "burnout" in str(mh.get("multi_label", [])) and distress < 0.6
    run_journaling = stability > 0.3 and emotion.get("mental_fatigue", 0.5) < 0.8 and receptiveness.journaling > 0.5
    
    # Modality
    core = emotion.get("core_emotion", "neutral")
    if core in ["anger", "fear", "grief"] and trust > 0.4:
        modality = "DBT"
    elif "burnout" in str(mh.get("multi_label", [])) and distress < 0.6:
        modality = "ACT"
    elif core in ["anxiety", "fear"] and trust < 0.4:
        modality = "Mindfulness"
    elif "depression" in str(mh.get("multi_label", [])) and distress < 0.5:
        modality = "MI"
    else:
        modality = "CBT"
    
    # FIXED: Add session_depth and alliance_score
    return EmotionalOperatingState(
        surface_emotion=emotion.get("surface_emotion", "neutral"),
        core_emotion=emotion.get("core_emotion", "neutral"),
        suppressed_emotion=emotion.get("suppressed_emotion"),
        emotional_stability=stability,
        mental_fatigue=emotion.get("mental_fatigue", 0.5),
        social_energy=emotion.get("social_energy", 0.5),
        distress_level=distress,
        trust_level=trust,
        attachment_style=user_history.get("attachment_style", "unknown") if user_history else "unknown",
        receptiveness=receptiveness,
        valence=emotion.get("valence", "neutral"),
        modality=modality,
        run_distortion=run_distortion,
        run_challenge=run_challenge,
        run_music=run_music,
        run_routine=run_routine,
        run_journaling=run_journaling,
        run_mindfulness=run_mindfulness,
        session_depth=0.0,  # FIXED
        alliance_score=0.0  # FIXED
    )