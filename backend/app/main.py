from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS
from .routes import router

# Load environment variables from .env if present
load_dotenv()

app = FastAPI(title="Agentic Honey-Pot Scam Detection API")
app.include_router(router)

# CORS for local UI + demo use
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve standalone UI at / (if frontend exists)
frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def serve_ui():
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "UI not found. Open /docs or add frontend/."}


@app.get("/health")
def health():
    return {"status": "ok"}
