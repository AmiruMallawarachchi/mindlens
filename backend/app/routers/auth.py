from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from app.db import get_database
from app.config import settings

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

@router.post("/register", response_model=TokenResponse)
async def register(user: UserRegister):
    db = get_database()
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed = pwd_context.hash(user.password)
    user_doc = {
        "email": user.email,
        "password_hash": hashed,
        "name": user.name,
        "preferred_name": user.name,
        "role": "user",
        "personality_score": 0.5,
        "attachment_style": "unknown",
        "session_count": 0,
        "created_at": datetime.utcnow(),
        "last_session_at": None
    }
    
    result = await db.users.insert_one(user_doc)
    token = create_access_token({"sub": str(result.inserted_id), "email": user.email})
    return TokenResponse(access_token=token)

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    db = get_database()
    user = await db.users.find_one({"email": credentials.email})
    if not user or not pwd_context.verify(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": str(user["_id"]), "email": user["email"]})
    return TokenResponse(access_token=token)