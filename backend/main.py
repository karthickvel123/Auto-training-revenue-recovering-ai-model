from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.database import init_db
from backend.webhook import router as webhook_router
from backend.api_routes import router as api_router
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logging.getLogger(__name__).info("Database initialized")
    yield

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

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def root():
    store_file = os.path.join(static_dir, "store.html")
    if os.path.exists(store_file):
        return FileResponse(store_file)
    return {"service": "Adaptive Revenue Recovery Agent", "status": "running"}

@app.get("/store")
def store():
    store_file = os.path.join(static_dir, "store.html")
    if os.path.exists(store_file):
        return FileResponse(store_file)
    return {"error": "Storefront not found"}

@app.get("/api/health")
def health():
    return {"service": "Adaptive Revenue Recovery Agent", "status": "healthy"}
