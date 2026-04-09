# Project Guidelines

## Overview

ETL pipeline that downloads, transforms, and publishes U.S. election results from multiple official sources. See [README.md](../README.md) for supported sources and published endpoints.

## Build and Test

```sh
pipenv install --dev          # install dependencies
pipenv run pre-commit install # install git hooks
pipenv run pytest             # run tests
make lint                     # flake8
make format                   # black auto-format
make mypy                     # type checking
make 2026-june-primary        # full pipeline for the 2026 June Primary
make bootstrap                # regenerate corrections.csv templates from raw data
```

Each pipeline stage runs as a Python module:
```sh
pipenv run python -m src.{source}.download --election 2026-june-primary
pipenv run python -m src.{source}.transform
pipenv run python -m src.optimize
pipenv run python -m src.export
pipenv run python -m src.upload kpcc
```

## Architecture

```
elections/
  {name}.yaml       # per-election config: LAC election_id, CA SOS slug list, client sources
src/
  {source}/
    download.py     # fetch raw data → data/raw/{source}/; accepts --election <name>
    transform.py    # normalize → data/transformed/{source}/
    bootstrap.py    # generate corrections.csv template from downloaded raw data
    corrections.csv # data correction lookup table (filters, renames, incumbents)
  schema.py         # Pydantic models: Contest + CandidateResult + BaseTransformer
  utils.py          # shared HTTP, file I/O, S3, load_election_config helpers
  optimize.py       # merge sources → data/optimized/{client}/
  export.py         # flatten optimized JSON → CSV
  upload.py         # push optimized/kpcc/latest.json to S3
```

Each stage writes a timestamped file **and** overwrites `latest.json` in the same directory.

## Conventions

### Adding a new source

1. Create `src/{source}/` with `__init__.py`, `download.py`, `transform.py`, `corrections.csv`
2. `download.py`: use `utils.request_json()` / `utils.request_html()`; write with `utils.write_json()`; paths from `utils.RAW_DATA_DIR / source_name`
3. `transform.py`: subclass `BaseTransformer` from `src.schema`; implement `transform_data()`, `include()`, and `correct_*()` methods; validate output via `.dump()`
4. Add source to the relevant optimize function in `src/optimize.py` if it feeds a client

### Transformer pattern

```python
class ContestTransformer(BaseTransformer):
    model = ContestModel   # Pydantic model (was schema = ContestSchema() in Marshmallow)

    def include(self) -> bool:          # return False to skip contest
        ...
    def transform_data(self) -> dict:   # return dict matching Contest model
        ...
```

- `corrections.csv` is the authority for contest names, descriptions, geography, level, sort order, and incumbent flags — raw data names are never trusted
- Slug uniqueness is enforced at optimize time (assertion); never produce duplicate slugs across sources
- All timestamps use `utils.now()` (America/Los_Angeles timezone)

### Schema fields

`Contest`: `name`, `slug`, `description`, `geography`, `level`, `precincts_reporting`, `candidates`, `sort_order`  
`CandidateResult`: `name`, `party`, `votes`, `votes_percent` (0–1 decimal), `incumbent`

See [src/schema.py](../src/schema.py) for full definitions.

## Environment

Requires a `.env` file with AWS credentials for S3 uploads:
```
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=
AWS_BUCKET=
AWS_PATH_PREFIX=   # optional
```

Corrections sheets are maintained in Google Sheets and published as CSV (**File → Share → Publish to web → CSV**). The lookup priority is:

1. `corrections_url` in the election YAML (preferred — per-election, per-source)
2. `LAC_CORRECTIONS_SHEET_URL` / `CA_SOS_CORRECTIONS_SHEET_URL` env vars (active-election override)
3. Local `corrections.csv` fallback (used by tests and offline dev)

To set a per-election corrections URL, add it to the election YAML:
```yaml
sources:
  los_angeles_county:
    corrections_url: https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}
  ca_secretary_of_state:
    corrections_url: https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development setup and release process.
