.PHONY: build up down restart logs frontend-dev backend-dev

# Docker Commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

# Local Development Commands
frontend-dev:
	cd frontend && pnpm run dev

backend-dev:
	cd backend && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
