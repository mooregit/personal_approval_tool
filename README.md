# P.A.T. - Personal Approval Tool

P.A.T. is a local human-in-the-loop approval queue for AI agents. Agents submit proposed actions,
P.A.T. records them, optionally asks a local Ollama model for analysis, and waits for a human
decision before anything meaningful is executed by the submitting system.

## Current v1 scope

- Local FastAPI web app with a static dashboard.
- SQLite persistence.
- API-key protected agent submission and decision endpoints.
- Immutable audit log for every proposal, enrichment, and decision.
- Ollama-powered analysis for summaries, risk review, suggested decision, and missing-field checks.
- Decision states: `pending`, `approved`, `rejected`, `edited`, `marked_wrong`, `expired`,
  `auto_approved`, and `cancelled`.
- Edited proposals preserve the original and create a new linked request.
- Placeholder auto-approval rule table for future user-selected remembered approvals.

## Project docs

Design and status docs live in [docs](docs/README.md). Start with:

- [Project Scope](docs/project-scope.md)
- [Architecture](docs/architecture.md)
- [Permission Model](docs/permission-model.md)
- [API Surface](docs/api-surface.md)
- [Operations](docs/operations.md)
- [Status](docs/status.md)

Forward-looking work is tracked in [TODO.md](TODO.md).

## Agent integration skill

Agents can use the repo-hosted skill in [skills/pat-approval](skills/pat-approval/SKILL.md). It tells
agents how to register with P.A.T., check policy before side effects, submit approval requests, and
wait for results.

The skill also includes a dependency-free Python client:

```bash
PAT_API_KEY=... python skills/pat-approval/scripts/pat_client.py
```

## Why no vector database yet?

Approval queues and audit trails are transactional records, not vector-search problems. SQLite is the
right first database for v1. A vector store can be added later if P.A.T. needs semantic search across
past approvals, memory retrieval, or similarity-based policy suggestions.

## Setup

```bash
cd /home/rmoore/dev/personal-approval-tool
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` and set `PAT_API_KEY` to a private local token.

## Database migrations

P.A.T. uses Alembic for SQLite schema migrations. The app runs migrations on startup, but you can also
run them manually:

```bash
.venv/bin/alembic upgrade head
```

Create future migrations with:

```bash
.venv/bin/alembic revision -m "describe schema change"
```

## Run

```bash
.venv/bin/uvicorn pat.app:app --reload --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`.

Ollama should be running separately, usually at `http://127.0.0.1:11434`. Set
`PAT_OLLAMA_MODEL` in `.env` to an installed model name such as `llama3.1:8b`.

## Submit an approval request

```bash
curl -X POST http://127.0.0.1:8765/api/approval-requests \
  -H "Authorization: Bearer dev-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "proposed_action": "create_follow_up_email",
    "source": "email-agent",
    "risk_level": "medium",
    "confidence": 0.82,
    "reason": "Interview occurred 5 days ago with no reply",
    "requires_approval": true,
    "payload": {
      "to": "person@example.com",
      "subject": "Following up",
      "body": "Thanks again for your time last week..."
    }
  }'
```

## Submit an email intake request

Email is an adapter into the normal approval queue. A future Gmail poller can parse Gmail messages and
call this endpoint.

```bash
curl -X POST http://127.0.0.1:8765/api/email-intake \
  -H "Authorization: Bearer dev-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "agent@example.com",
    "to": "approval@example.com",
    "subject": "Approve follow-up email",
    "body": "Please review this proposed follow-up email before sending.",
    "message_id": "email-123",
    "thread_id": "thread-456",
    "action_hint": "create_follow_up_email",
    "risk_level": "medium",
    "confidence": 0.82,
    "requires_approval": true
  }'
```

## Poll for a decision

Agents can poll the result endpoint after submitting a request.

```bash
curl http://127.0.0.1:8765/api/approval-requests/2/result \
  -H "Authorization: Bearer dev-change-me"
```

Pending requests return `terminal: false`. Approved requests return `approved: true` and an
`action_to_execute` object containing the exact proposal payload the agent should execute.

There is also a minimal polling agent example:

```bash
PAT_API_KEY=dev-change-me python examples/polling_agent.py
```

## Decision callbacks

Requests can include `callback_url`. When a decision is made, P.A.T. makes one immediate `POST` to
that URL with the same core result shape returned by `/result`. Callback attempts are recorded in the
request audit log as `callback.delivered` or `callback.failed`.

## Permission policies

P.A.T. can act as the local permission authority for agents. Agents can ask whether an action is
allowed, blocked, auto-approved, or requires approval before they submit a full approval request.

Register an agent:

```bash
curl -X POST http://127.0.0.1:8765/api/agents/register \
  -H "Authorization: Bearer dev-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "email-agent",
    "display_name": "Email Agent",
    "description": "Drafts and routes email approval requests.",
    "callback_url": "http://127.0.0.1:9000/pat-callback",
    "capabilities": ["read_email", "draft_email", "send_email"]
  }'
```

Unknown agents that call `/api/policy/check` are automatically registered as `new`. New agents always
require manual approval until you activate them:

```bash
curl -X PATCH http://127.0.0.1:8765/api/agents/email-agent \
  -H "Authorization: Bearer dev-change-me" \
  -H "Content-Type: application/json" \
  -d '{"status": "active"}'
```

Inspect an agent's effective permissions:

```bash
curl http://127.0.0.1:8765/api/agents/email-agent/permissions \
  -H "Authorization: Bearer dev-change-me"
```

This returns the agent, enabled global policies that apply to it, enabled agent-specific policies, and
recent policy checks for that agent. Agent-specific policies have `"scope": "agent"`; global policies
have `"scope": "global"`.

Create a policy:

```bash
curl -X POST http://127.0.0.1:8765/api/policies \
  -H "Authorization: Bearer dev-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "External emails require approval",
    "agent": "email-agent",
    "action": "send_email",
    "resource": "gmail",
    "conditions": {
      "recipient_scope": "external"
    },
    "decision": "require_approval",
    "risk_level": "medium",
    "priority": 10
  }'
```

Check policy:

```bash
curl -X POST http://127.0.0.1:8765/api/policy/check \
  -H "Authorization: Bearer dev-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "email-agent",
    "action": "send_email",
    "resource": "gmail",
    "context": {
      "recipient_scope": "external",
      "has_attachment": false
    }
  }'
```

Policy decisions are `allow`, `require_approval`, `deny`, `auto_approve`, and `log_only`. If no
enabled policy matches, P.A.T. defaults to `require_approval`.

## Service mode

P.A.T. can run continuously as a Linux systemd user service:

```bash
scripts/install-user-service.sh
systemctl --user status pat.service
journalctl --user -u pat.service -f
```

See [Operations](docs/operations.md) for manual install commands and service notes.
