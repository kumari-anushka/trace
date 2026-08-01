FROM python:3.13-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv==0.9.13

COPY pyproject.toml uv.lock ./

FROM base AS development

RUN uv sync --frozen --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src

EXPOSE 8000

CMD ["sh", "-c", "uv sync --frozen --no-install-project && exec /app/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"]

FROM base AS production

RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
