#!/usr/bin/env python3
"""Minimal agent-side example for submitting to P.A.T. and polling for a decision."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

PAT_BASE_URL = os.environ.get("PAT_BASE_URL", "http://127.0.0.1:8765")
PAT_API_KEY = os.environ.get("PAT_API_KEY", "dev-change-me")


def request_json(path: str, *, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{PAT_BASE_URL}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {PAT_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"P.A.T. request failed: {exc.code} {detail}") from exc


def main() -> None:
    created = request_json(
        "/api/approval-requests",
        method="POST",
        body={
            "proposed_action": "update_task",
            "source": "example-polling-agent",
            "risk_level": "low",
            "confidence": 0.9,
            "reason": "Demo task update waiting for human approval.",
            "requires_approval": True,
            "payload": {"task_id": "demo-123", "status": "done"},
            "metadata": {"example": True},
        },
    )

    print(f"Submitted approval request #{created['id']}")

    while True:
        result = request_json(f"/api/approval-requests/{created['id']}/result")
        print(f"Current status: {result['status']}")

        if result["terminal"]:
            break
        time.sleep(3)

    if result["approved"]:
        print("Approved action:")
        print(json.dumps(result["action_to_execute"], indent=2))
    else:
        print(f"Not approved: {result['status']}")
        if result["decision_note"]:
            print(result["decision_note"])


if __name__ == "__main__":
    main()
