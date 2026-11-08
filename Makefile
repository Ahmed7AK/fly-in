VENV    := .venv
PYTHON  := $(VENV)/bin/python
MAP     ?= maps/example.txt

.PHONY: install run debug clean lint lint-strict

install:
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) main.py $(MAP)

debug:
	$(PYTHON) -m pdb main.py $(MAP)

clean:
	rm -rf __pycache__ */__pycache__ .mypy_cache

lint:
	$(PYTHON) -m flake8 .
	$(PYTHON) -m mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	$(PYTHON) -m flake8 .
	$(PYTHON) -m mypy . --strict
