"""Code Audit - FastAPI Application Entry Point"""

import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import init_db
from app.api.routes import projects, audits, llm, dashboard, keys, skills, mcp

# Resolve frontend dist path: project_root/frontend/dist
# __file__ = backend/app/main.py → backend/app → backend → project_root
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))   # backend/app
_BACKEND_ROOT = os.path.dirname(_BACKEND_DIR)                  # backend
_PROJECT_ROOT = os.path.dirname(_BACKEND_ROOT)                 # code-audit/
_FRONTEND_DIST = os.path.join(_PROJECT_ROOT, "frontend", "dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print(f"  Database initialized")
    if os.path.isdir(_FRONTEND_DIST):
        print(f"  Frontend dist found at {_FRONTEND_DIST}")
    else:
        print(f"  [WARNING] Frontend dist not found at {_FRONTEND_DIST}")
        print(f"  Run: cd frontend && npm run build")
    yield
    print(f"  Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered code security audit platform",
    lifespan=lifespan,
)

# CORS (needed for dev mode with separate vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(projects.router)
app.include_router(audits.router)
app.include_router(llm.router)
app.include_router(dashboard.router)
app.include_router(keys.router)
app.include_router(skills.router)
app.include_router(mcp.router)


@app.get("/")
async def root():
    # Serve index.html if frontend is built
    index_path = os.path.join(_FRONTEND_DIST, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "message": "Frontend not built. Run: cd frontend && npm run build",
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve frontend static assets (js, css, images, etc.)
if os.path.isdir(_FRONTEND_DIST):
    # Mount static directories that exist
    assets_dir = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # SPA fallback: any non-/api route serves index.html
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Try to serve a real file first
        file_path = os.path.join(_FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # Fallback to index.html for client-side routing
        index_path = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return {"detail": "Not found"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
