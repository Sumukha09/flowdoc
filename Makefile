.PHONY: help up down restart logs ps migrate downgrade test health clean

COMPOSE     := docker compose
APP_SERVICE := backend

help:
	@echo "FlowDocs - common targets:"
	@echo "  make up        Start PostgreSQL, apply migrations, and start the app"
	@echo "  make down      Stop services and keep database data"
	@echo "  make restart   Restart services"
	@echo "  make logs      Follow backend logs"
	@echo "  make ps        Show container status"
	@echo "  make migrate   Apply Alembic migrations"
	@echo "  make downgrade Roll back the last Alembic migration"
	@echo "  make test      Run backend tests in the container"
	@echo "  make health    Check the API health endpoint"
	@echo "  make clean     Stop services and delete database data"

up:
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm $(APP_SERVICE) alembic upgrade head
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f $(APP_SERVICE)

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) run --rm $(APP_SERVICE) alembic upgrade head

downgrade:
	$(COMPOSE) exec $(APP_SERVICE) alembic downgrade -1

test:
	$(COMPOSE) exec $(APP_SERVICE) pytest -v

health:
	curl -fsS http://localhost:8000/health

clean:
	$(COMPOSE) down -v
