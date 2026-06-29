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

## Linux user service

P.A.T. can run continuously as a systemd user service.

Install and start using the helper:

```bash
scripts/install-user-service.sh
```

The helper writes:

```text
~/.config/systemd/user/pat.service
```

It uses the current checkout path, `.env`, and `.venv/bin/uvicorn`.

Manual install:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/pat.service.example ~/.config/systemd/user/pat.service
systemctl --user daemon-reload
systemctl --user enable --now pat.service
```

If you copy the example manually, edit `WorkingDirectory`, `EnvironmentFile`, and `ExecStart` first.

Service commands:

```bash
systemctl --user status pat.service
systemctl --user restart pat.service
systemctl --user stop pat.service
journalctl --user -u pat.service -f
```

To let user services continue after logout:

```bash
loginctl enable-linger "$USER"
```

## Verification

```bash
.venv/bin/pytest
.venv/bin/ruff check .
```

## Service state

The repo includes a systemd user service template and install helper. The helper does not commit or
modify `.env`; it only requires that `.env` exists locally.
