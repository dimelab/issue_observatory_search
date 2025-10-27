from __future__ import annotations

"""Authentication schemas."""
from datetime import datetime
from typing import TYPE_CHECKING
from pydantic import BaseModel, EmailStr, Field


class TokenData(BaseModel):
    """Data stored in JWT token."""

    username: str | None = None
    user_id: int | None = None


class LoginRequest(BaseModel):
    """Login request."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class UserCreate(BaseModel):
    """User creation schema."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    is_admin: bool = False


class UserResponse(BaseModel):
    """User response schema."""

    id: int
    username: str
    email: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    last_login: datetime | None = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class UserUpdate(BaseModel):
    """User update schema."""

    email: EmailStr | None = None
    password: str | None = Field(None, min_length=6)
    is_active: bool | None = None


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
