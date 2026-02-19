"""
Auth Router
============

Simple authentication endpoint.
Credentials are loaded from environment variables (not hardcoded).
"""

import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class LoginResponse(BaseModel):
    success: bool
    role: str = "guest"
    username: str = ""
    message: str = ""


def _get_users() -> dict:
    """Load user credentials from environment variables."""
    users = {}
    admin_user = os.getenv("AUTH_ADMIN_USER", "admin")
    admin_pass = os.getenv("AUTH_ADMIN_PASSWORD", "")
    guest_user = os.getenv("AUTH_GUEST_USER", "guest")
    guest_pass = os.getenv("AUTH_GUEST_PASSWORD", "")

    if admin_pass:
        users[admin_user] = {"password": admin_pass, "role": "admin"}
    if guest_pass:
        users[guest_user] = {"password": guest_pass, "role": "guest"}

    return users


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user. Credentials are stored in .env, NOT in frontend code.
    """
    users = _get_users()

    if not users:
        logger.warning("[Auth] No auth credentials configured in .env — allowing any login as guest")
        return LoginResponse(
            success=True,
            role="guest",
            username=request.username,
            message="No credentials configured — default guest access"
        )

    user = users.get(request.username)
    if user and user["password"] == request.password:
        return LoginResponse(
            success=True,
            role=user["role"],
            username=request.username,
            message="Login successful"
        )

    raise HTTPException(status_code=401, detail="Invalid username or password")
