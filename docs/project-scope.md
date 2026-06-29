# Project Scope

P.A.T. is a local-first permission and approval authority for AI agent workflows.

The core idea is simple: agents can propose actions, ask what needs approval, and receive a clear
human-reviewed decision before meaningful side effects happen.

## Goals

- Run locally on the user's machine.
- Use local models through Ollama for review assistance, not final authority.
- Provide a reusable approval queue for other agents and tools.
- Centralize permission policy for agents.
- Preserve an immutable audit trail for proposals, policy checks, decisions, and callbacks.
- Keep action execution outside P.A.T.; the submitting agent executes only after approval.
- Stay portable across machines, starting with Linux.

## Non-goals

- P.A.T. should not directly send emails, create calendar events, or modify external systems.
- P.A.T. should not become a general agent runtime.
- P.A.T. should not rely on cloud LLMs for core behavior.
- P.A.T. should not auto-approve actions unless the user has explicitly configured policy allowing it.

## Primary users

- The local human operator who owns final authority.
- Local or personal agents that need permission checks and approval handoff.
- Future orchestration tools that need a consistent human-in-the-loop primitive.

## Current product shape

- FastAPI backend.
- SQLite database.
- Alembic migrations.
- Static local web dashboard.
- Ollama enrichment for approval request analysis.
- API-key protected local API.
