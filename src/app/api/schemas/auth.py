from __future__ import annotations

from pydantic import BaseModel


class AuthLoginRequest(BaseModel):
    password: str


class AuthSessionResponse(BaseModel):
    authenticated: bool
