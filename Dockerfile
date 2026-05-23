# Dev-oriented image: bind-mount the repo at /app in docker-compose so
# --reload sees host edits; venv lives outside /app so the mount does not
# clobber it.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

RUN uv venv /opt/venv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY static ./static

RUN uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "panstwa_miasta.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws-max-size", "262144"]
