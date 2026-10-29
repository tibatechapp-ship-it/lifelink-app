# LifeLink — unified dev commands
#
# One entrypoint for contributors and CI. The single definition of "green"
# is `make check` (lint + tests); `make test` is the test gate alone.

PY ?= python3

.PHONY: help install test lint check run clean

help:
	@echo "lifelink — available targets:"
	@echo ""
	@echo "  make install   — install runtime + dev dependencies"
	@echo "  make test      — pytest suite"
	@echo "  make lint      — ruff check ."
	@echo "  make check     — lint + tests (the single 'green' definition)"
	@echo "  make run       — local dev server (sqlite, FLASK_ENV=development)"
	@echo "  make clean     — remove caches and the local sqlite database"

install:
	$(PY) -m pip install -r requirements.txt -r requirements-dev.txt

test:
	$(PY) -m pytest tests/ -q

lint:
	$(PY) -m ruff check .

check: lint test

run:
	FLASK_ENV=development $(PY) app.py

clean:
	find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache 2>/dev/null || true
	rm -f lifelink.db 2>/dev/null || true
