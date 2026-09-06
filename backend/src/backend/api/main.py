"""Main FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import guide, profile, search, settings

app = FastAPI(
    title="OpenGuide API",
    version="0.1.0",
    description="开源项目新手贡献智能向导 —— 仓库画像 / 视角索引 / 指南生成",
)

# Dev default: allow the Vite dev server (5173) and any localhost origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(search.router)
app.include_router(guide.router)
app.include_router(settings.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
