.PHONY: install check test lint typecheck data reproduce audit clean

install:
	pip install -e ".[dev]"

check: lint typecheck test

lint:
	ruff check src tests
	ruff format --check src tests

typecheck:
	mypy

test:
	pytest

data:
	ctb fetch all --data data

reproduce:
	ctb reproduce --data data --work work

clean:
	rm -rf work .pytest_cache .mypy_cache .ruff_cache
