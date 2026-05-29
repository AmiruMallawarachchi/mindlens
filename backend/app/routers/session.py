from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional
from datetime import datetime
from app.db import get_database

router = APIRouter()

@router.websocket("/session/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: Optional[str] = None):
    await websocket.accept()
    db = get_database()
    
    session_data = {
        "session_id": session_id,
        "messages": [],
        "turn_count": 0,
        "started_at": datetime.utcnow()
    }
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")
            
            if msg_type == "message":
                content = data.get("content", "")
                session_data["turn_count"] += 1
                
                # Placeholder response for Day 1 testing
                response = {
                    "type": "response",
                    "content": f"Echo: {content} (Turn {session_data['turn_count']})",
                    "metadata": {"turn": session_data["turn_count"]}
                }
                
                await websocket.send_json(response)
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
        print(f"Session {session_id} saved. Turns: {session_data['turn_count']}")