from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional
from datetime import datetime
from app.db import get_database
from app.agents.safety_gate import safety_gate, CRISIS_TEMPLATES
from app.agents.orchestrator import run_inference, build_eos

router = APIRouter()

@router.websocket("/session/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: Optional[str] = None):
    await websocket.accept()
    db = get_database()
    
    session_data = {
        "session_id": session_id,
        "messages": [],
        "turn_count": 0,
        "started_at": datetime.utcnow(),
        "safety_events": []
    }
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")
            
            if msg_type == "message":
                content = data.get("content", "")
                session_data["turn_count"] += 1
                
                # ===== SAFETY GATE (unbypassable) =====
                safety_result = await safety_gate(content)
                
                if not safety_result["safe"]:
                    # Log safety event
                    session_data["safety_events"].append({
                        "turn": session_data["turn_count"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "severity": safety_result["severity_score"]
                    })
                    
                    # Crisis response (ZERO LLM)
                    template = CRISIS_TEMPLATES["severe"] if safety_result["severity_score"] > 0.75 else CRISIS_TEMPLATES["moderate"]
                    
                    await websocket.send_json({
                        "type": "crisis",
                        "content": template,
                        "metadata": {
                            "show_crisis_banner": True,
                            "resources": safety_result["resources"],
                            "severity": safety_result["severity_score"]
                        }
                    })
                    continue
                
                # ===== ORCHESTRATOR: Run models, build EOS =====
                inference = await run_inference(content)
                eos = build_eos(inference, user_history={})
                
                # ===== THERAPY RESPONSE (placeholder) =====
                reflection = f"It sounds like you're experiencing {eos.core_emotion}. "
                if eos.distress_level > 0.7:
                    reflection += "I can tell this is really heavy right now."
                else:
                    reflection += "I'm here to help you work through this."
                
                await websocket.send_json({
                    "type": "response",
                    "content": reflection,
                    "metadata": {
                        "eos": eos.to_dict(),
                        "modality": eos.modality,
                        "interventions": {
                            "music": eos.run_music,
                            "mindfulness": eos.run_mindfulness,
                            "journaling": eos.run_journaling,
                            "challenge": eos.run_challenge,
                            "routine": eos.run_routine
                        },
                        "turn": session_data["turn_count"]
                    }
                })
                
                session_data["messages"].append({
                    "role": "user",
                    "content": content,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            elif msg_type == "mood_update":
                await db.mood_logs.insert_one({
                    "session_id": session_id,
                    "mood_score": data.get("mood_score", 5),
                    "timestamp": datetime.utcnow()
                })
                
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        session_data["ended_at"] = datetime.utcnow()
        await db.sessions.insert_one(session_data)
        print(f"Session {session_id} saved. Turns: {session_data['turn_count']}, Safety events: {len(session_data['safety_events'])}")