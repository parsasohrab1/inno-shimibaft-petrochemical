"""FastAPI entrypoint for SPRO (scaffold).

SPRO = Smart Process, Energy & Production Optimization, PetroPala Toos'
proposed product for Shimi Baft Petrochemical Company (proposal letter
ref. 14050616001, dated 1405/06/16). See docs/SRS.md for the full
requirements and docs/vendor-proposal-reference.md for the source letter
text this scaffold was built from.

Run it with:
    pip install -r requirements.txt
    uvicorn app.main:app --app-dir backend --port 8000

Then open http://127.0.0.1:8000/docs for the interactive API docs, or
http://127.0.0.1:8000/ once the frontend has been built (``npm run
build`` inside frontend/, which writes to frontend/dist).
"""
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import connect, init_db, scalar
from .routers import auth, energy_feedstock, forecasting_decision, process_intelligence, quality_prediction

log = logging.getLogger("spro")
_state = {"seeding": False, "ready": False, "training_models": False, "models_ready": False}


def _ensure_data():
    from .seed import seed
    _state["seeding"] = True
    try:
        seed()
    except Exception:  # pragma: no cover
        log.exception("seeding failed")
    finally:
        _state.update(seeding=False, ready=True)


def _ensure_models():
    """Background-train modules 1-4's real models on synthetic data if no
    cached artifact bundle exists yet — mirrors ``_ensure_data`` above.
    Trained on synthetic data only; see backend/app/ml/__init__.py.
    """
    from .ml import registry
    from .ml.train import train_all

    if registry.is_ready():
        _state["models_ready"] = True
        return
    _state["training_models"] = True
    try:
        train_all(out_dir=config.MODELS_DIR, n_points=config.TRAIN_N_POINTS, seed=config.TRAIN_SEED)
    except Exception:  # pragma: no cover
        log.exception("model training failed")
    finally:
        _state.update(training_models=False, models_ready=registry.is_ready())


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    conn = connect()
    empty = scalar(conn, "SELECT COUNT(*) FROM users") == 0
    conn.close()
    if empty and config.AUTO_SEED:
        threading.Thread(target=_ensure_data, daemon=True).start()
    else:
        _state["ready"] = True
    if config.AUTO_TRAIN_MODELS:
        threading.Thread(target=_ensure_models, daemon=True).start()
    else:
        from .ml import registry as _registry

        _state["models_ready"] = _registry.is_ready()
    yield


app = FastAPI(
    title="SPRO — بهینه‌سازی هوشمند فرآیند، انرژی و تولید (شیمی بافت)",
    version="0.1.0-scaffold",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing(request: Request, call_next):
    t = time.time()
    resp = await call_next(request)
    resp.headers["X-Process-Time"] = f"{time.time() - t:.3f}"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):  # pragma: no cover
    log.exception("unhandled error")
    return JSONResponse({"detail": "خطای داخلی سرور"}, status_code=500)


@app.get("/health")
def health():
    return {"status": "ok" if _state["ready"] else "seeding", **_state, "product": "SPRO", "scaffold": True}


for r in (auth.router, process_intelligence.router, energy_feedstock.router, quality_prediction.router, forecasting_decision.router):
    app.include_router(r)

if config.FRONTEND_DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(config.FRONTEND_DIST_DIR / "index.html")
