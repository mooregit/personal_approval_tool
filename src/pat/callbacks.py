from typing import Any

import httpx


def build_callback_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": result["id"],
        "status": result["status"],
        "approved": result["approved"],
        "terminal": result["terminal"],
        "action_to_execute": result["action_to_execute"],
        "decision_note": result["decision_note"],
        "decided_by": result["decided_by"],
        "decided_at": result["decided_at"],
    }


async def deliver_callback(callback_url: str, result: dict[str, Any]) -> dict[str, Any]:
    payload = build_callback_payload(result)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(callback_url, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "delivered": False,
            "url": callback_url,
            "error": str(exc),
        }

    return {
        "delivered": True,
        "url": callback_url,
        "status_code": response.status_code,
    }
