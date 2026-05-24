# Dev-oriented image: bind-mount the repo at /app in docker-compose so
# --reload sees host edits; venv lives outside /app so the mount does not
# clobber it.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

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

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "panstwa_miasta.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws-max-size", "262144"]
