# OpenGuide backend image (FastAPI + 四视角索引 + 指南生成).
#
# Build context is ./backend. Dependencies come from uv.lock so the image is
# reproducible and matches local dev / CI.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# uv pinned to a known version (matches the lock's revision) installed from
# PyPI, so the build does not depend on a container-registry tag existing.
RUN pip install --no-cache-dir "uv==0.12.23"

WORKDIR /app

# Dependency layer first so source edits don't bust the cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY README.md ./
COPY src ./src
COPY tests ./tests
COPY conftest.py ./

# Vector store persists here; docker-compose mounts a named volume on it.
ENV VECTORSTORE_DIR=/app/.chroma
RUN mkdir -p /app/.chroma

EXPOSE 8000

# 0.0.0.0 is required so the port is reachable from outside the container.
CMD ["uv", "run", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
