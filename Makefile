SHELL := /bin/sh

POSTGRES_DB ?= trace
POSTGRES_USER ?= trace
POSTGRES_PASSWORD ?= trace

-include .env

TEST_DATABASE_URL ?= postgresql+psycopg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:5432/$(POSTGRES_DB)
TEST_REDIS_URL ?= redis://localhost:6379/0

.PHONY: help setup hooks infra migrate dev backend-dev frontend-dev test test-backend test-frontend lint lint-backend lint-frontend format docker-build down

help:
	@echo "Trace development commands"
	@echo ""
	@echo "  make setup          Install backend, frontend, and hook tooling"
	@echo "  make infra          Start PostgreSQL and Redis, then apply migrations"
	@echo "  make migrate        Apply all pending database migrations"
	@echo "  make backend-dev    Run the backend locally with reload"
	@echo "  make frontend-dev   Run the frontend locally"
	@echo "  make dev            Run the complete stack in Docker"
	@echo "  make test           Run backend tests and build the frontend"
	@echo "  make lint           Run all formatting, lint, and type checks"
	@echo "  make format         Format backend and frontend source"
	@echo "  make docker-build   Build production container targets"
	@echo "  make down           Stop the Docker stack"

setup:
	cd backend && uv sync --frozen
	npm --prefix frontend ci
	uv tool install pre-commit
	uv tool run pre-commit install

hooks:
	uv tool run pre-commit install

infra:
	docker compose up -d --wait postgres redis
	$(MAKE) migrate

migrate:
	cd backend && DATABASE_URL="$(TEST_DATABASE_URL)" REDIS_URL="$(TEST_REDIS_URL)" uv run alembic upgrade head

dev:
	docker compose --profile app up --build

backend-dev:
	cd backend && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

frontend-dev:
	npm --prefix frontend run dev -- --host 0.0.0.0 --port 5173

test: test-backend test-frontend

test-backend:
	cd backend && DATABASE_URL="$(TEST_DATABASE_URL)" REDIS_URL="$(TEST_REDIS_URL)" uv run pytest

test-frontend:
	npm --prefix frontend run build

lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff format --check .
	cd backend && uv run ruff check .
	cd backend && uv run mypy .

lint-frontend:
	npm --prefix frontend run format:check
	npm --prefix frontend run lint

format:
	cd backend && uv run ruff format .
	cd backend && uv run ruff check --fix .
	npm --prefix frontend run format

docker-build:
	docker build --target production -t trace-backend ./backend
	docker build --target production -t trace-frontend ./frontend

down:
	docker compose --profile app down
