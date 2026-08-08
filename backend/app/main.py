import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .auth import seed_demo_users, UPLOAD_ROLES
from .data_dictionary import CANONICAL_FIELDS
from .db import Base, SessionLocal, engine
from .models import DataDictionaryEntry
from .routers import admin, auth, dashboard, quarantine, statements

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Financial Statement Data Governance Demo")

# Only needed for local dev (Vite on :5173 talking to the API on :8000). The
# production build is served by this same app (see the static mount below),
# so real deployments are same-origin and don't need CORS at all.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(statements.router)
app.include_router(quarantine.router)
app.include_router(dashboard.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo_users(db)
        for entry in CANONICAL_FIELDS:
            existing = db.get(DataDictionaryEntry, entry["field_name"])
            if not existing:
                db.add(DataDictionaryEntry(**entry))
        db.commit()
    finally:
        db.close()

    if not os.environ.get("UPLOAD_ROLE_PASSWORD"):
        logger.warning(
            "UPLOAD_ROLE_PASSWORD is not set - anyone can log in as %s and trigger "
            "billed Claude API calls. Set this env var before sharing a public link.",
            ", ".join(sorted(UPLOAD_ROLES)),
        )


@app.get("/api/health")
def health():
    return {"status": "ok"}


# --- Serve the built React frontend (production only) ---
# `frontend/dist` only exists after `npm run build`; local dev runs Vite
# separately on :5173, so this whole block is a no-op there.
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        # Any path FastAPI hasn't already matched (i.e. not /api/*) falls
        # through to here. Serve the real file if it exists (favicon, etc.),
        # otherwise hand back index.html so React Router can take over -
        # this is what makes deep links like /statements/5 work on refresh.
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
