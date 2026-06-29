#!/usr/bin/env python3
"""Small dependency-free client for P.A.T. agent integrations."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class PatError(RuntimeError):
    """Raised when P.A.T. rejects or cannot process a request."""


@dataclass(frozen=True)
class PatClient:
    base_url: str
    api_key: str

    @classmethod
    def from_env(cls) -> PatClient:
        api_key = os.environ.get("PAT_API_KEY")
        if not api_key:
            raise PatError("PAT_API_KEY is required")
        return cls(
            base_url=os.environ.get("PAT_BASE_URL", "http://127.0.0.1:8765"),
            api_key=api_key,
        )

    def request(self, path: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status == 204:
                    return None
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise PatError(f"P.A.T. request failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise PatError(f"P.A.T. is unreachable: {exc}") from exc

    def register_agent(
        self,
        *,
        agent: str,
        display_name: str | None = None,
        description: str | None = None,
        callback_url: str | None = None,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "/api/agents/register",
            method="POST",
            body={
                "agent": agent,
                "display_name": display_name,
                "description": description,
                "callback_url": callback_url,
                "capabilities": capabilities or [],
                "metadata": metadata or {},
            },
        )

    def check_policy(
        self,
        *,
        agent: str,
        action: str,
        resource: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "/api/policy/check",
            method="POST",
            body={
                "agent": agent,
                "action": action,
                "resource": resource,
                "context": context or {},
            },
        )

    def submit_approval_request(
        self,
        *,
        proposed_action: str,
        source: str,
        payload: dict[str, Any],
        risk_level: str = "unknown",
        confidence: float | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "/api/approval-requests",
            method="POST",
            body={
                "proposed_action": proposed_action,
                "source": source,
                "risk_level": risk_level,
                "confidence": confidence,
                "reason": reason,
                "requires_approval": True,
                "payload": payload,
                "metadata": metadata or {},
                "callback_url": callback_url,
            },
        )

    def get_result(self, request_id: int) -> dict[str, Any]:
        return self.request(f"/api/approval-requests/{request_id}/result")

    def wait_for_result(
        self,
        request_id: int,
        *,
        poll_seconds: float = 3.0,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        while True:
            result = self.get_result(request_id)
            if result["terminal"]:
                return result
            if timeout_seconds is not None and time.monotonic() - started > timeout_seconds:
                raise PatError(f"Timed out waiting for approval request {request_id}")
            time.sleep(poll_seconds)

    def check_then_request(
        self,
        *,
        agent: str,
        action: str,
        resource: str | None,
        context: dict[str, Any],
        payload: dict[str, Any],
        risk_level: str = "unknown",
        reason: str | None = None,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        policy = self.check_policy(
            agent=agent,
            action=action,
            resource=resource,
            context=context,
        )
        decision = policy["decision"]

        if decision == "deny":
            raise PatError(policy["reason"])

        if policy["requires_approval"]:
            request = self.submit_approval_request(
                proposed_action=action,
                source=agent,
                payload=payload,
                risk_level=risk_level,
                reason=reason or policy["reason"],
                metadata={"resource": resource, **context},
                callback_url=callback_url,
            )
            return {"policy": policy, "approval_request": request}

        return {"policy": policy, "approval_request": None}


def main() -> None:
    agent = os.environ.get("PAT_AGENT_ID", "example-agent")
    client = PatClient.from_env()
    registration = client.register_agent(
        agent=agent,
        display_name="Example Agent",
        description="Smoke-test P.A.T. integration client.",
        capabilities=["demo_action"],
    )
    print(json.dumps(registration, indent=2))
    policy = client.check_policy(
        agent=agent,
        action="demo_action",
        resource="demo",
        context={"example": True},
    )
    print(json.dumps(policy, indent=2))


if __name__ == "__main__":
    main()
