.DEFAULT_GOAL := help

.PHONY: help install dev-web dev-api test lint typecheck build db-up db-down migrate gmi-smoke

help:
	@printf '%s\n' 'Fit Check commands:' \
	  '  make install     Install web and API dependencies' \
	  '  make dev-web     Start Next.js on :3000' \
	  '  make dev-api     Start FastAPI on :8000' \
	  '  make test        Run API tests' \
	  '  make lint        Run API and web lint checks' \
	  '  make typecheck   Run API and web type checks' \
	  '  make build       Build the web app' \
	  '  make db-up       Start local PostgreSQL' \
	  '  make db-down     Stop local PostgreSQL' \
	  '  make migrate     Apply API database migrations' \
	  '  make gmi-smoke   Run the explicitly enabled GMI capability probe'

install:
	npm install
	cd services/api && uv sync --all-groups

dev-web:
	npm run dev:web

dev-api:
	cd services/api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	cd services/api && uv run pytest

lint:
	cd services/api && uv run ruff check .
	npm run lint:web

typecheck:
	cd services/api && uv run mypy app
	npm run typecheck:web

build:
	npm run build:web

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
	cd services/api && uv run alembic upgrade head

gmi-smoke:
	cd services/api && uv run python -m app.scripts.gmi_smoke_test
