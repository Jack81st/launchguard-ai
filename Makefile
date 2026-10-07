.PHONY: install test lint eval serve demo clean

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install -e ".[dev]"

test:
	.venv/bin/pytest --cov=launchguard --cov-report=term-missing

lint:
	.venv/bin/ruff check src tests
	.venv/bin/python -m compileall -q src

eval:
	.venv/bin/launchguard eval

serve:
	.venv/bin/launchguard serve

demo:
	.venv/bin/launchguard start --catalog examples/catalog.csv --sku LG-BTL-001 --offline

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
