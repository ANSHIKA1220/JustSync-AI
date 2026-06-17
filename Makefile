install:
	cd apps/api && py -m pip install -r requirements.txt
	cd apps/web && npm.cmd install

dev:
	docker compose up --build

build:
	cd apps/web && npm.cmd run build

test:
	cd apps/api && py -m pytest
	cd apps/web && npm.cmd test

lint:
	cd apps/api && py -m ruff check app tests
	cd apps/web && npm.cmd run lint

seed:
	cd apps/api && py -m app.seed

reset-demo:
	cd apps/api && py -m app.seed --reset

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v
