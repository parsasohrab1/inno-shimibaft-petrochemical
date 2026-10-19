import time
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_conn, one, rows
from ..schemas import LoginRequest
from ..security import ROLES, create_token, current_user, require, verify_password

router = APIRouter(prefix="/api", tags=["auth"])
_fails: dict[str, list[float]] = {}


@router.post("/auth/login")
def login(body: LoginRequest, conn: sqlite3.Connection = Depends(get_conn)):
    now = time.time()
    recent = [t for t in _fails.get(body.username, []) if now - t < 300]
    if len(recent) >= 5:
        raise HTTPException(429, "تعداد تلاش ناموفق زیاد است؛ ۵ دقیقه بعد دوباره تلاش کنید")
    u = one(conn, "SELECT * FROM users WHERE username=?", (body.username,))
    if not u or not u["is_active"] or not verify_password(body.password, u["password_hash"]):
        _fails[body.username] = recent + [now]
        raise HTTPException(401, "نام کاربری یا گذرواژه نادرست است")
    _fails.pop(body.username, None)
    return {
        "access_token": create_token(u),
        "token_type": "bearer",
        "user": {"username": u["username"], "full_name": u["full_name"], "role": u["role"], "role_fa": ROLES.get(u["role"])},
    }


@router.get("/auth/me")
def me(user: sqlite3.Row = Depends(current_user)):
    return {**dict(user), "role_fa": ROLES.get(user["role"])}


@router.get("/users")
def users(conn: sqlite3.Connection = Depends(get_conn), _=Depends(require())):
    return rows(conn, "SELECT user_id, username, full_name, role, is_active FROM users ORDER BY user_id")
