"""Module 3 API — Smart Quality Prediction & Off-Spec Detection."""
import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_conn
from ..security import current_user
from ..services import quality_prediction as svc

router = APIRouter(prefix="/api/quality", tags=["module-3-quality-prediction"])


@router.get("/offspec-risk")
def offspec_risk(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return svc.offspec_risk(conn)


@router.get("/model-predictions")
def model_predictions(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    """FR-M3-01/02/03 — real purity regression + 30-min-ahead OOS classifier
    + feature-importance ranking, applied to the latest live-ish tag values."""
    return svc.model_predictions(conn)
