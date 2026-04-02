.PHONY: install dev seed test lint docker clean

install:
	pip install -e ".[dev]"

dev:
	uvicorn entity_resolution.main:app --reload --host 0.0.0.0 --port 8000

seed:
	python -m scripts.seed_db

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

docker:
	docker compose up --build

clean:
	rm -f data/*.db
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf *.egg-info
	rm -rf build dist
