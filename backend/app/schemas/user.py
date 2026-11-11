import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    role: Literal["ATTENDEE", "ORGANISER"] = "ATTENDEE"  # ADMIN can never be self-assigned

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain at least one letter and one number")
        return v

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=64)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until the token expires")
    user: UserOut


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=64)


class AdminUserUpdate(BaseModel):
    role: Literal["ATTENDEE", "ORGANISER", "ADMIN"] | None = None
    is_active: bool | None = None
