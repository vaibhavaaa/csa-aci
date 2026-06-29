from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.database import Base, engine
from app.core.config import ALLOWED_ORIGINS
from app.auth.routes import router as auth_router
from app.api.tasks import router as task_router
from app.websocket.manager import manager
from app.websocket.routes import router as ws_router
from app.websocket.redis_listener import redis_listener

from app.models.user import User  # noqa: F401 — needed for Base.metadata
from app.models.task import Task  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup:
      1. Create DB tables (idempotent).
      2. Open the async Redis connection on the ConnectionManager.
      3. Launch the Redis pub/sub listener as a background task.

    Shutdown:
      1. Cancel the listener task and wait for it to exit cleanly.
      2. Close the Redis connection.
    """
    # ── startup ──────────────────────────────────────────────────────
    Base.metadata.create_all(bind=engine)

    await manager.connect_redis()

    listener_task = asyncio.create_task(
        redis_listener(),
        name="redis_listener",
    )
    logger.info("Redis pub/sub listener started.")

    yield  # app runs here

    # ── shutdown ─────────────────────────────────────────────────────
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass  # expected — listener exits cleanly on cancel

    await manager.disconnect_redis()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="Cognitive Agent Platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # env-driven allow-list (see core/config.py)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(task_router)
app.include_router(ws_router)

# Expose Prometheus metrics at /metrics (HTTP request latency/count/size
# histograms). Scraped by the in-cluster Prometheus — see
# infra/deployment/monitoring/. Instrument here, after routers are mounted.
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/")
def root():
    return {"status": "running"}


@app.get("/healthz")
def healthz():
    """Liveness/readiness probe target (see infra/deployment manifests)."""
    return {"status": "ok"}