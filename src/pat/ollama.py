import json
from typing import Any

import httpx

from pat.config import Settings
from pat.models import ApprovalRequestCreate

SYSTEM_PROMPT = """You analyze proposed actions from local AI agents for a human approval queue.
Return compact JSON only with these keys:
summary: string,
risk_review: string,
suggested_decision: one of approve, reject, edit, inspect,
missing_fields: string[],
concerns: string[].
Do not claim the action was performed. You are only reviewing a proposal."""


async def analyze_request(
    settings: Settings,
    request: ApprovalRequestCreate,
) -> dict[str, Any] | None:
    if not settings.enable_ollama:
        return None

    prompt = {
        "proposed_action": request.proposed_action,
        "source": request.source,
        "risk_level_from_agent": request.risk_level,
        "confidence_from_agent": request.confidence,
        "reason_from_agent": request.reason,
        "requires_approval_from_agent": request.requires_approval,
        "payload": request.payload,
        "metadata": request.metadata,
    }

    try:
        async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=10.0) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "model": settings.ollama_model,
                    "stream": False,
                    "format": "json",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": json.dumps(prompt)},
                    ],
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "summary": "Ollama analysis unavailable.",
            "risk_review": "P.A.T. stored the request without local model enrichment.",
            "suggested_decision": "inspect",
            "missing_fields": [],
            "concerns": [str(exc)],
            "analysis_error": True,
        }

    data = response.json()
    content = data.get("message", {}).get("content", "{}")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {
            "summary": content[:500],
            "risk_review": "Model returned non-JSON analysis.",
            "suggested_decision": "inspect",
            "missing_fields": [],
            "concerns": ["Non-JSON model response"],
            "analysis_error": True,
        }

    return parsed
