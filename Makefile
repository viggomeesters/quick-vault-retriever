.PHONY: setup format lint typecheck test contracts privacy check build

setup:
	uv sync --all-groups

format:
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	@if [ -d src ]; then uv run ty check src; fi

test:
	@if [ -d tests ]; then uv run pytest; fi

contracts:
	uv run python scripts/validate_design.py
	./go validate .

privacy:
	@bash scripts/check.sh >/dev/null
	@echo "privacy gate: passed"

check:
	bash scripts/check.sh

build:
	uv build
