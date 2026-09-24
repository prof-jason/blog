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
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev
COPY backend/app ./app
COPY frontend/src/data/subjects.json ./subjects.json
COPY --from=frontend /frontend/out ./static

ENV PATH="/app/.venv/bin:$PATH" \
    STATIC_DIR=/app/static \
    SUBJECTS_PATH=/app/subjects.json \
    DATABASE_PATH=/app/data/app.db
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
