PYTHON ?= python
VENV = . .venv/bin/activate &&

.PHONY: install test train-atp train-wta gate-atp gate-wta validate sync-atp sync-wta

install:
	uv venv
	$(VENV) uv pip install -e ".[dev]"

test:
	$(VENV) pytest

sync-atp:
	$(VENV) tennis-predict --tour atp sync-data --refresh

sync-wta:
	$(VENV) tennis-predict --tour wta sync-data --refresh

train-atp:
	$(VENV) tennis-predict --tour atp run-pipeline --refresh-data

train-wta:
	$(VENV) tennis-predict --tour wta run-pipeline --refresh-data

gate-atp:
	@bash gate.sh atp

gate-wta:
	@bash gate.sh wta

validate: gate-atp gate-wta
