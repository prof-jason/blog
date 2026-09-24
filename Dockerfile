# --- Build the Next.js frontend as a static export ---
FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- FastAPI backend serving the API and the exported frontend ---
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev
COPY backend/app ./app
COPY backend/subjects.json ./subjects.json
COPY --from=frontend /frontend/out ./static
# The database is recreated here on every start, so only this directory is writable by the app.
RUN mkdir -p /app/data && chown app:app /app/data

ENV PATH="/app/.venv/bin:$PATH" \
    STATIC_DIR=/app/static \
    SUBJECTS_PATH=/app/subjects.json \
    DATABASE_PATH=/app/data/app.db
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
