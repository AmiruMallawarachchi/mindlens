from fastapi import APIRouter
from app.db import get_database
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/mood-trend")
async def get_mood_trend(user_id: str, days: int = 7):
    db = get_database()
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    logs = await db.mood_logs.find({
        "user_id": user_id,
        "timestamp": {"$gte": cutoff}
    }).sort("timestamp", 1).to_list(length=100)
    
    return {
        "data": [
            {
                "date": log["timestamp"].strftime("%Y-%m-%d") if hasattr(log["timestamp"], "strftime") else str(log["timestamp"]),
                "score": log["mood_score"]
            }
            for log in logs
        ]
    }

@router.get("/session-history")
async def get_session_history(user_id: str, limit: int = 10):
    db = get_database()
    
    sessions = await db.sessions.find({
        "user_id": user_id
    }).sort("started_at", -1).limit(limit).to_list(length=limit)
    
    return {
        "sessions": [
            {
                "id": str(s["_id"]),
                "started_at": s.get("started_at"),
                "turn_count": s.get("turn_count", 0),
                "modality": s.get("modality", "CBT")
            }
            for s in sessions
        ]
    }