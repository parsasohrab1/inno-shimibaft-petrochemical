"""Module 2 API — Smart Energy & Feedstock Optimization."""
import sqlite3

from fastapi import APIRouter, Depends, Query

from ..db import get_conn
from ..security import current_user
from ..services import energy_feedstock as svc

router = APIRouter(prefix="/api/energy-feedstock", tags=["module-2-energy-feedstock"])


@router.get("/intensity")
def intensity(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return svc.energy_intensity(conn)


@router.get("/feed-batches")
def feed_batches(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return svc.feed_constraints(conn)


@router.post("/optimize-mix")
def optimize_mix(
    energy_budget_gj: float | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_conn),
    _=Depends(current_user),
):
    return svc.recommend_production_mix(conn, energy_budget_gj=energy_budget_gj)
