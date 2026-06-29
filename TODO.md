# P.A.T. TODO

## Near term

- Build dashboard views for agents, policies, and policy check history.
- Add a guided onboarding flow for `new` agents.
- Add a policy editor UI with condition validation.
- Reduce repeated Alembic startup logs by running migrations once per process lifecycle.
- Add secure API key generation/setup command.
- Add desktop notifications for pending approvals and new agent onboarding.

## Platform hardening

- Add callback retry queue with backoff and max attempts.
- Add policy import/export.
- Add database backup/export command.
- Add request expiration handling.
- Add audit log filters and export.
- Add structured application logging.
- Add rate limiting or separate scoped API keys for agents.

## Integrations

- Gmail API polling adapter.
- Calendar approval adapter.
- Task-system adapter.
- GitHub issue/PR action adapter.
- Filesystem operation adapter.

## Later

- User-approved remembered decisions that create policy suggestions.
- Semantic search over prior decisions and policies.
- Optional vector store for memory/policy similarity, if justified by usage.
- Multi-machine sync model.
- Signed agent identities rather than shared bearer-token trust.
