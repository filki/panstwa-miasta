# Dev-oriented image: bind-mount the repo at /app in docker-compose so
# --reload sees host edits; venv lives outside /app so the mount does not
# clobber it.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

# --- JS deps (cache layer: rarely changes) ---
COPY package.json package-lock.json ./
RUN npm ci

# --- Python deps (cache layer: rarely changes) ---
RUN uv venv /opt/venv
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen

# --- App source + static ---
COPY src ./src
COPY static ./static

# --- Build Tailwind CSS ---
RUN npm run css:build

# --- Non-root user (security) ---
RUN groupadd -r app && useradd -r -g app -d /app app && \
    chown -R app:app /app /opt/venv
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uv", "run", "uvicorn", "panstwa_miasta.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws-max-size", "262144"]
