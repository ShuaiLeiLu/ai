from __future__ import annotations

from pydantic import Field

from app.schemas.common import SchemaModel


class LoginRequest(SchemaModel):
    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=6, max_length=128)


class RegisterRequest(SchemaModel):
    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=6, max_length=128)
    nickname: str = Field(min_length=1, max_length=32)


class UserProfile(SchemaModel):
    user_id: str
    phone: str
    nickname: str
    membership_level: str
    battery_balance: int


class AuthToken(SchemaModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile
