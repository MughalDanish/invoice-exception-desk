.PHONY: up migrate seed test demo down

up:
	docker compose up -d --build

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python -m app.seed

test:
	docker compose exec backend python -c "import os,pytest; os.environ['TEST_DATABASE_URL']=os.environ['DATABASE_URL']; raise SystemExit(pytest.main(['-q']))"

demo: up migrate seed
	docker compose exec backend python -m app.smoke

down:
	docker compose down
