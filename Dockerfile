FROM node:22.22.2-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12.10-slim-bookworm AS backend
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY ffv2/ ffv2/
COPY pipeline/ pipeline/
COPY analysis/ analysis/
COPY migrations/ migrations/
COPY alembic.ini ./
COPY --from=frontend /build/dist frontend/dist
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app app && mkdir /app/data && chown app:app /app/data
USER 10001:10001
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
LABEL org.opencontainers.image.title="Failure Forensics" org.opencontainers.image.version="2.0.0-dev"
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live',timeout=3)"
CMD ["python", "-m", "uvicorn", "ffv2.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
