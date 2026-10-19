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
    """Module 4 — one append-only accept/reject audit entry (NFR-06).

    Never mutates the original recommendations row; see
    services/forecasting_decision.py's ``record_decision``.
    """

    status: str  # "accepted" | "rejected"
    note: str | None = None


class AddRecommendationRequest(BaseModel):
    module: str
    title: str
    detail: str | None = None
    impact: str | None = None
    confidence: float = 0.5
    suggested_action: dict | None = None
    expected_effect: dict | None = None
