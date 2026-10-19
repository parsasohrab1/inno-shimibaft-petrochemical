"""Module 1 API — Process Intelligence & Operating-Condition Optimization."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_conn
from ..security import current_user
from ..services import process_intelligence as svc

router = APIRouter(prefix="/api/process-intelligence", tags=["module-1-process-intelligence"])


@router.get("/tags")
def tags(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return svc.list_tags(conn)


@router.get("/tags/{tag_id}/envelope")
def tag_envelope(tag_id: str, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    result = svc.tag_envelope(conn, tag_id)
    if result is None:
        raise HTTPException(404, "تگ یافت نشد")
    return result


@router.get("/variability-flags")
def variability_flags(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return svc.variability_flags(conn)


@router.get("/operating-envelopes")
def operating_envelopes(_=Depends(current_user)):
    """FR-M1-02 — trained data-driven envelopes + 95% CI for all modelled tags."""
    return svc.operating_envelopes()


@router.get("/productivity-correlation")
def productivity_correlation(_=Depends(current_user)):
    """FR-M1-03 — measured multivariate R^2 against the productivity proxy."""
    return svc.productivity_correlation()
