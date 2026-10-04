# AI Apprentice - backend developer tasks.
#
# NOTE: always invoke tools via "$(PY) -m ..." rather than venv/bin/<tool>.
# Console scripts hardcode an absolute shebang, so they break if the
# virtualenv is moved. See `make venv` to rebuild.

PY      := venv/bin/python
PIP     := $(PY) -m pip
UVICORN := $(PY) -m uvicorn
APP     := app.main:app
REQS    := requirements.txt

HOST ?= 0.0.0.0
PORT ?= 8000

.DEFAULT_GOAL := help
.PHONY: help venv deps run test test-verbose test-e2e db-init clean distclean

help: ## Show available targets
	@echo "AI Apprentice backend"
	@echo
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-13s\033[0m %s\n", $$1, $$2}'
	@echo

# Only fires when the interpreter is absent, to give a useful message
# instead of a bare "No such file or directory".
$(PY):
	@echo "error: $(PY) not found. Create the environment with: make venv"
	@exit 1

venv: ## Create the virtualenv and install dependencies
	python3 -m venv venv
	$(PIP) install --upgrade pip
	$(PIP) install -r $(REQS)

deps: $(PY) ## Install/refresh dependencies in the existing virtualenv
	$(PIP) install -r $(REQS)

run: $(PY) ## Start the API with autoreload on $(HOST):$(PORT)
	$(UVICORN) $(APP) --reload --host $(HOST) --port $(PORT)

test: $(PY) ## Run the test suite
	$(PY) -m pytest -q

test-verbose: $(PY) ## Run the test suite verbosely
	$(PY) -m pytest -v

test-e2e: $(PY) ## Run only the full capture/map/teach loop test
	$(PY) -m pytest tests/test_e2e.py -v

db-init: $(PY) ## Create tables in the configured database
	$(PY) -c "from app.db.init_db import init_db; init_db(); print('database initialised')"

clean: ## Remove caches and bytecode
	rm -rf .pytest_cache htmlcov .ruff_cache
	find . -type d -name __pycache__ -not -path './venv/*' -prune -exec rm -rf {} +
	find . -type f -name '*.py[co]' -not -path './venv/*' -delete

distclean: clean ## Also remove the virtualenv
	rm -rf venv