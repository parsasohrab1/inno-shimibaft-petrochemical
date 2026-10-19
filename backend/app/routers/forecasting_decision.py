"""Module 4 API — Production Forecasting & Real-Time Operational Decision Support."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_conn
from ..schemas import RecommendationAction, WhatIfRequest
from ..security import current_user
from ..services import forecasting_decision as svc

router = APIRouter(prefix="/api/forecast", tags=["module-4-forecasting-decision"])


@router.get("/outlook")
def outlook(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return svc.outlook(conn)


@router.post("/what-if")
def what_if(body: WhatIfRequest, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return svc.what_if(conn, body.parameter, body.delta_pct, body.note)


@router.get("/recommendations")
def recommendations(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return svc.list_recommendations(conn)


@router.post("/recommendations/{rec_id}/status")
def set_status(rec_id: int, body: RecommendationAction, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    if body.status not in ("accepted", "rejected"):
        raise HTTPException(400, "وضعیت نامعتبر است")
    svc.set_recommendation_status(conn, rec_id, body.status)
    return {"id": rec_id, "status": body.status}
