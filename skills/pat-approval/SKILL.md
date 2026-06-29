---
name: pat-approval
description: Use when an agent needs to integrate with P.A.T. (Personal Approval Tool) as a local policy and human-approval authority before taking side-effectful actions such as sending email, modifying files, creating issues, updating calendars, saving memory, or changing external systems.
---

# P.A.T. Approval Integration

Use P.A.T. before any action that can create, modify, delete, send, persist, publish, or otherwise
affect user data or external systems.

P.A.T. owns permission policy. The agent owns action execution. The user owns final authority.

## Required Configuration

Read these from the environment when possible:

- `PAT_BASE_URL`, default `http://127.0.0.1:8765`
- `PAT_API_KEY`, required for protected endpoints
- optional `PAT_AGENT_ID`, stable agent identifier
- optional `PAT_CALLBACK_URL`, callback endpoint controlled by the agent

If `PAT_API_KEY` is unavailable, do not perform side-effectful actions that require P.A.T. approval.

## Core Workflow

1. Register the agent on startup or first use:

   `POST /api/agents/register`

2. Before side effects, check policy:

   `POST /api/policy/check`

3. Follow the returned decision:

   - `deny`: stop; do not perform the action.
   - `require_approval`: submit an approval request and wait for approval.
   - `auto_approve`: execute only if the response says no manual approval is required.
   - `allow`: execute without manual approval.
   - `log_only`: execute if otherwise safe, but treat the check as audited.

4. If approval is required, submit:

   `POST /api/approval-requests`

5. Wait for the result:

   - Poll `GET /api/approval-requests/{id}/result`, or
   - Provide `callback_url` and handle the callback.

6. Execute only the returned `action_to_execute` when `approved` is `true`.

## Agent Registration

Register with a stable `agent` value. Do not invent a different name per run.

```json
{
  "agent": "email-agent",
  "display_name": "Email Agent",
  "description": "Drafts and routes email approval requests.",
  "callback_url": "http://127.0.0.1:9000/pat-callback",
  "capabilities": ["read_email", "draft_email", "send_email"]
}
```

Unknown agents are auto-registered as `new`. A `new` agent will receive `require_approval` with
`requires_onboarding: true` until the user activates it in P.A.T.

## Policy Check Shape

Use action/resource names that are stable and specific.

```json
{
  "agent": "email-agent",
  "action": "send_email",
  "resource": "gmail",
  "context": {
    "recipient_scope": "external",
    "has_attachment": false
  }
}
```

Context should contain non-secret summary facts needed for policy matching, not full private payloads
unless necessary.

## Approval Request Shape

When policy requires approval, send the full proposed action:

```json
{
  "proposed_action": "send_email",
  "source": "email-agent",
  "risk_level": "medium",
  "confidence": 0.82,
  "reason": "External recipient requires human review.",
  "requires_approval": true,
  "callback_url": "http://127.0.0.1:9000/pat-callback",
  "payload": {
    "to": "person@example.com",
    "subject": "Following up",
    "body": "..."
  },
  "metadata": {
    "resource": "gmail",
    "recipient_scope": "external"
  }
}
```

## Result Handling

Only execute when:

```json
{
  "terminal": true,
  "approved": true,
  "action_to_execute": {
    "proposed_action": "send_email",
    "payload": {}
  }
}
```

If `approved` is false, stop. If status is `edited`, use the new linked approval request created by
P.A.T. rather than executing the original payload.

## Bundled Client

Use `scripts/pat_client.py` for a dependency-free Python client. It supports registration, policy
checks, approval submission, polling, and a `check_then_request` helper.

Run directly for a smoke test:

```bash
PAT_API_KEY=... python skills/pat-approval/scripts/pat_client.py
```
