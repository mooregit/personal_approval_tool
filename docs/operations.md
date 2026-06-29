# Operations

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
```

Set `PAT_API_KEY` in `.env`.

## Run locally

```bash
.venv/bin/uvicorn pat.app:app --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

## Ollama

Ollama should be running locally, usually at:

```text
http://127.0.0.1:11434
```

Set `PAT_OLLAMA_MODEL` to an installed model name. On this machine the working model has been:

```text
llama3.1:8b
```

If Ollama is unavailable, approval requests are still stored and the analysis records an unavailable
state.

## Migrations

P.A.T. uses Alembic.

Apply migrations:

```bash
.venv/bin/alembic upgrade head
```

Create a migration:

```bash
.venv/bin/alembic revision -m "describe change"
```

The app currently runs migrations at startup through `Database.init()`.

## Verification

```bash
.venv/bin/pytest
.venv/bin/ruff check .
```

## Current service state

P.A.T. is ready to be run as a Linux user service, but the systemd unit has not been added yet.
