.PHONY: install dev seed test lint format typecheck check coverage docker clean

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

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

typecheck:
	mypy

check: lint typecheck test

coverage:
	pytest tests/ -v --cov=entity_resolution --cov-report=term-missing --cov-report=html

docker:
	docker compose up --build

clean:
	rm -f data/*.db
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache htmlcov
	rm -rf *.egg-info
	rm -rf build dist
