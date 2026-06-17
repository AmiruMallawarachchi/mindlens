"""
MindLens Authentication Router

Handles user registration, login, JWT token generation, and token validation.
Uses bcrypt for password hashing and JWT for stateless authentication.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.config import settings
from backend.app.db import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])

# --- Security Setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# --- Pydantic Schemas ---


class UserRegister(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=13, le=100)
    nickname: Optional[str] = Field(None, max_length=100)


class UserLogin(BaseModel):
    """Request body for user login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response containing JWT access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """Public user profile (returned after registration/login)."""

    id: str
    email: str
    name: str
    nickname: Optional[str]
    age: int
    age_group: str
    created_at: datetime


# --- Helper Functions ---


def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, email: str) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: MongoDB document _id as string
        email: User's email address
        
    Returns:
        Encoded JWT string
    """
    now = datetime.utcnow()
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    
    payload = {
        "sub": user_id,           # subject = user ID
        "email": email,
        "iat": now,               # issued at
        "exp": expire,            # expiration
        "type": "access",
    }
    
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Validate JWT token and return current user document.
    
    Used as a dependency in protected routes.
    """
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no subject",
            )
            
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    # Fetch user from MongoDB
    user = await db.users.find_one({"_id": user_id})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user


# --- Routes ---


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(user_data: UserRegister, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Register a new MindLens user.
    
    - Checks for duplicate email
    - Hashes password with bcrypt
    - Determines age group (teen vs adult)
    - Returns JWT access token
    """
    # Check if email already exists
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    # Determine age group
    age_group = "teen" if user_data.age <= 19 else "adult"
    
    # Create user document
    user_doc = {
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
        "name": user_data.name,
        "nickname": user_data.nickname or user_data.name,
        "age": user_data.age,
        "age_group": age_group,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "is_active": True,
        "onboarding_complete": False,
    }
    
    # Insert into MongoDB
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    # Generate JWT
    token = create_access_token(user_id, user_data.email)
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login existing user",
)
async def login(credentials: UserLogin, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Authenticate a user and return a JWT access token.
    
    - Finds user by email
    - Verifies password with bcrypt
    - Returns JWT on success
    """
    # Find user by email
    user = await db.users.find_one({"email": credentials.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Verify password
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated",
        )
    
    # Generate JWT
    user_id = str(user["_id"])
    token = create_access_token(user_id, credentials.email)
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Return the current authenticated user's profile.
    
    Requires valid JWT in Authorization header.
    """
    return UserResponse(
        id=str(current_user["_id"]),
        email=current_user["email"],
        name=current_user["name"],
        nickname=current_user.get("nickname"),
        age=current_user["age"],
        age_group=current_user["age_group"],
        created_at=current_user["created_at"],
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout user",
)
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout endpoint.
    
    Note: JWT is stateless, so true logout requires token blocklisting.
    For now, this is a client-side operation (delete token from storage).
    """
    return {"message": "Logged out successfully"}


# --- Admin Route (for testing) ---


@router.get(
    "/users/count",
    summary="Get total user count (admin)",
)
async def get_user_count(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Return total number of registered users.
    
    Protected: requires valid authentication.
    """
    count = await db.users.count_documents({})
    return {"total_users": count}