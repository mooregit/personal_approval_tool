#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${SERVICE_DIR}/pat.service"
UVICORN_BIN="${PROJECT_DIR}/.venv/bin/uvicorn"
ENV_FILE="${PROJECT_DIR}/.env"

if [[ ! -x "${UVICORN_BIN}" ]]; then
  echo "Missing ${UVICORN_BIN}. Run: .venv/bin/pip install -e \".[dev]\"" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Run: cp .env.example .env and set PAT_API_KEY." >&2
  exit 1
fi

mkdir -p "${SERVICE_DIR}"

cat > "${SERVICE_FILE}" <<SERVICE
[Unit]
Description=P.A.T. Personal Approval Tool
Documentation=https://github.com/mooregit/personal_approval_tool
After=network.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${UVICORN_BIN} pat.app:app --host 127.0.0.1 --port 8765
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
SERVICE

systemctl --user daemon-reload
systemctl --user enable --now pat.service

echo "Installed and started ${SERVICE_FILE}"
echo "Status: systemctl --user status pat.service"
echo "Logs:   journalctl --user -u pat.service -f"
