"""Module 4 API — Production Forecasting & Real-Time Operational Decision Support."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_conn
from ..schemas import AddRecommendationRequest, RecommendationAction, WhatIfRequest
from ..security import current_user
from ..services import forecasting_decision as svc

router = APIRouter(prefix="/api/forecast", tags=["module-4-forecasting-decision"])


@router.get("/outlook")
def outlook(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return svc.outlook(conn)


@router.post("/what-if")
def what_if(body: WhatIfRequest, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return svc.what_if(conn, body.parameter, body.delta_pct, body.note)


@router.get("/scenarios")
def rank_operating_scenarios(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    """FR-M4-03 — >=3 re-simulated, multi-criteria-ranked operating scenarios."""
    return svc.rank_operating_scenarios(conn)


@router.get("/recommendations")
def recommendations(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return svc.list_recommendations(conn)


@router.post("/recommendations")
def create_recommendation(
    body: AddRecommendationRequest, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)
):
    rec_id = svc.add_recommendation(
        conn,
        module=body.module,
        title=body.title,
        detail=body.detail,
        impact=body.impact,
        confidence=body.confidence,
        suggested_action=body.suggested_action,
        expected_effect=body.expected_effect,
    )
    return {"id": rec_id}


@router.post("/recommendations/auto-generate")
def auto_generate_recommendation(conn: sqlite3.Connection = Depends(get_conn), user=Depends(current_user)):
    """Generate a recommendation from the real module-3 OOS estimate, with
    a suggested_action + expected_effect computed via module 4's
    re-simulation (FR-M4-02)."""
    result = svc.auto_recommend_from_quality(conn, actor_username=user["username"])
    if result is None:
        return {"generated": False, "note": "برآورد خلوص فعلی به‌قدر کافی داخل مشخصه است یا مدل‌ها آموزش‌دیده نیستند"}
    return {"generated": True, **result}


@router.post("/recommendations/{rec_id}/status")
def set_status(
    rec_id: int, body: RecommendationAction, conn: sqlite3.Connection = Depends(get_conn), user=Depends(current_user)
):
    """NFR-06 — append-only audit trail: writes a NEW
    ``recommendation_decisions`` row; never mutates the original
    recommendation. See services/forecasting_decision.record_decision.
    """
    if body.status not in ("accepted", "rejected"):
        raise HTTPException(400, "وضعیت نامعتبر است")
    svc.record_decision(conn, rec_id, body.status, actor_username=user["username"], note=body.note)
    return {"id": rec_id, "status": body.status}
