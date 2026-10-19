"""Pydantic request/response models shared across routers.

Kept intentionally small for this scaffold; most endpoints currently
return plain dicts built in the services layer. Add typed schemas here as
each module's real logic is implemented.
"""
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class WhatIfRequest(BaseModel):
    """Module 4 — hypothetical change to a process/feed/energy parameter."""

    parameter: str
    delta_pct: float
    note: str | None = None


class RecommendationAction(BaseModel):
    status: str  # "accepted" | "rejected"
