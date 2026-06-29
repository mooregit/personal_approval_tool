import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def json_loads(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


class Database:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        config = Config(str(project_root() / "alembic.ini"))
        config.set_main_option("script_location", str(project_root() / "migrations"))
        config.set_main_option("sqlalchemy.url", f"sqlite:///{self.path.resolve()}")
        command.upgrade(config, "head")


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def row_to_request(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "parent_id": row["parent_id"],
        "proposed_action": row["proposed_action"],
        "source": row["source"],
        "risk_level": row["risk_level"],
        "confidence": row["confidence"],
        "reason": row["reason"],
        "requires_approval": bool(row["requires_approval"]),
        "status": row["status"],
        "payload": json_loads(row["payload_json"]),
        "metadata": json_loads(row["metadata_json"]),
        "llm_analysis": json_loads(row["llm_analysis_json"]),
        "correlation_id": row["correlation_id"],
        "callback_url": row["callback_url"],
        "decision_note": row["decision_note"],
        "decided_by": row["decided_by"],
        "decided_at": row["decided_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "expires_at": row["expires_at"],
    }


def row_to_audit_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "request_id": row["request_id"],
        "event_type": row["event_type"],
        "actor": row["actor"],
        "details": json_loads(row["details_json"]),
        "created_at": row["created_at"],
    }


def row_to_policy(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "enabled": bool(row["enabled"]),
        "agent": row["agent"],
        "action": row["action"],
        "resource": row["resource"],
        "conditions": json_loads(row["conditions_json"]),
        "decision": row["decision"],
        "risk_level": row["risk_level"],
        "priority": row["priority"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_policy_check_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "policy_id": row["policy_id"],
        "agent_status": row["agent_status"] if "agent_status" in row.keys() else None,
        "agent": row["agent"],
        "action": row["action"],
        "resource": row["resource"],
        "context": json_loads(row["context_json"]),
        "decision": row["decision"],
        "requires_approval": bool(row["requires_approval"]),
        "reason": row["reason"],
        "created_at": row["created_at"],
    }


def row_to_agent(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "agent": row["agent"],
        "display_name": row["display_name"],
        "description": row["description"],
        "status": row["status"],
        "callback_url": row["callback_url"],
        "capabilities": json_loads(row["capabilities_json"]),
        "metadata": json_loads(row["metadata_json"]),
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
