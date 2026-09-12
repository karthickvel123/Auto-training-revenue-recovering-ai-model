"""FastAPI application entry point for the Adaptive Revenue Recovery Agent."""
import os
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import init_db, get_session_local
from backend.webhook import router as webhook_router
from backend.api_routes import router as api_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def _escalation_loop():
    """Background worker that periodically checks for stale recovery attempts and escalates them."""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        try:
            from backend.escalation_engine import check_and_escalate
            SessionLocal = get_session_local()
            db = SessionLocal()
            try:
                check_and_escalate(db)
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Escalation loop error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized")
    task = asyncio.create_task(_escalation_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Adaptive Revenue Recovery Agent",
    description="AI-powered payment recovery with deterministic safety rules",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(api_router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def root():
    """Serve the VoltStore customer storefront."""
    store_file = os.path.join(static_dir, "store.html")
    if os.path.exists(store_file):
        return FileResponse(store_file)
    return {"service": "Adaptive Revenue Recovery Agent", "status": "running"}


@app.get("/store")
def store():
    """Alias route for the storefront."""
    store_file = os.path.join(static_dir, "store.html")
    if os.path.exists(store_file):
        return FileResponse(store_file)
    return {"error": "Storefront not found"}


@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"service": "Adaptive Revenue Recovery Agent", "status": "healthy"}
