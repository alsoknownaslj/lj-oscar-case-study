.PHONY: fetch cache profile db lint test sql-check

fetch:        ## download the 3 datasets (+ brief PDF) from Google Drive into data/raw/
	python scripts/fetch_data.py

cache:        ## build faithful all-string parquet mirrors in data/cache/
	python scripts/build_cache.py

profile:      ## profile raw tables and rewrite the AUTO section of the data dictionary
	python scripts/profile_data.py

db:           ## build self-contained data/oscar.duckdb (tables + model views) for IDE browsing
	python scripts/build_db.py

lint:         ## format + lint python
	ruff format scripts src tests
	ruff check --fix scripts src tests

sql-check:    ## lint saved SQL
	sqlfluff lint sql/ || true

test:
	python -m pytest
