# Architecture

P.A.T. is a local web application with a backend API, a SQLite database, and a static dashboard.

## Components

- `pat.app`: FastAPI application and HTTP route definitions.
- `pat.repository`: database access and domain behavior.
- `pat.models`: Pydantic request/response models and enums.
- `pat.database`: SQLite connection management and Alembic migration entry point.
- `pat.ollama`: local Ollama analysis integration.
- `pat.callbacks`: callback payload construction and one-shot callback delivery.
- `src/pat/static`: browser dashboard assets.
- `migrations`: Alembic migration environment and versioned schema changes.
- `examples`: simple agent-side examples.

```mermaid
flowchart LR
    Human["Human operator"]
    Agent["External/local agents"]
    Browser["Local dashboard"]
    API["FastAPI app\npat.app"]
    Repo["Repository/domain layer\npat.repository"]
    DB[("SQLite\nP.A.T. database")]
    Alembic["Alembic migrations"]
    Ollama["Ollama local LLM"]
    Callback["Agent callback URL"]

    Human --> Browser
    Browser --> API
    Agent -->|"policy check / approval request"| API
    API --> Repo
    Repo --> DB
    Alembic --> DB
    API -->|"optional analysis"| Ollama
    API -->|"decision callback"| Callback
    Agent -->|"poll result"| API
```

## Data flow

1. Agent registers or calls `POST /api/policy/check`.
2. P.A.T. auto-registers unknown agents as `new`.
3. P.A.T. applies agent status gating.
4. Active agents are evaluated against enabled policies.
5. If approval is required, the agent submits an approval request.
6. P.A.T. stores the proposal and asks Ollama for optional review analysis.
7. The human approves, rejects, edits, marks wrong, expires, cancels, or auto-approves through policy.
8. The submitting agent polls `/result` or receives a callback.
9. The agent executes only the approved `action_to_execute`.

```mermaid
sequenceDiagram
    participant A as Agent
    participant P as P.A.T. API
    participant D as SQLite
    participant L as Ollama
    participant H as Human

    A->>P: POST /api/policy/check
    P->>D: touch/register agent and evaluate policy
    D-->>P: policy result
    P-->>A: allow / deny / require_approval / auto_approve
    alt requires approval
        A->>P: POST /api/approval-requests
        P->>D: store request
        P->>L: analyze request
        L-->>P: summary/risk review
        P->>D: store analysis audit
        H->>P: POST /decision
        P->>D: store decision
        P-->>A: callback, if configured
        A->>P: GET /result
        P-->>A: action_to_execute when approved
    end
```

## Trust boundary

P.A.T. currently uses a shared bearer token. Any process with that token can call the API, so the
agent registry is an accountability and policy layer, not strong identity. A future version should add
per-agent credentials or signed local identities.

## Persistence

SQLite is the source of truth. Alembic manages schema migrations.

Transactional records are stored relationally. A vector database is intentionally not part of v1
because approval queues, policies, and audit logs need exact filtering and deterministic behavior.

## Execution boundary

P.A.T. does not execute domain actions. It returns decisions and approved payloads. Agents are
responsible for execution and for honoring P.A.T.'s response.

## Database shape

```mermaid
erDiagram
    AGENTS ||--o{ POLICY_CHECK_EVENTS : "performs"
    PERMISSION_POLICIES ||--o{ POLICY_CHECK_EVENTS : "matches"
    APPROVAL_REQUESTS ||--o{ APPROVAL_REQUESTS : "edited into"
    APPROVAL_REQUESTS ||--o{ AUDIT_EVENTS : "records"

    AGENTS {
        int id
        text agent
        text status
        text capabilities_json
        text first_seen_at
        text last_seen_at
    }

    PERMISSION_POLICIES {
        int id
        text agent
        text action
        text resource
        text conditions_json
        text decision
        int priority
    }

    POLICY_CHECK_EVENTS {
        int id
        int policy_id
        text agent
        text agent_status
        text action
        text decision
    }

    APPROVAL_REQUESTS {
        int id
        int parent_id
        text proposed_action
        text source
        text status
        text payload_json
    }

    AUDIT_EVENTS {
        int id
        int request_id
        text event_type
        text actor
        text details_json
    }
```
