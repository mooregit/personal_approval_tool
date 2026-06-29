# Security Notes

P.A.T. is local-first software, but it stores sensitive operational data:

- approval requests
- policy checks
- agent metadata
- audit events
- local API keys

Do not commit local runtime data or secrets.

Ignored by default:

- `.env`
- `.env.*`
- `.venv/`
- `data/`
- SQLite database files
- logs
- caches
- generated package metadata

Use `.env.example` only for placeholder configuration. Set a private `PAT_API_KEY` in your local
`.env` before running the app outside throwaway development.

Current limitation: P.A.T. uses a shared bearer token. Any process with that token can call protected
endpoints. Per-agent credentials or signed local identities are planned future hardening work.
