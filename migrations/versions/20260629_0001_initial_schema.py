"""Initial P.A.T. schema.

Revision ID: 20260629_0001
Revises:
Create Date: 2026-06-29
"""

import sqlalchemy as sa
from alembic import op

revision = "20260629_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("PRAGMA journal_mode = WAL")

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("approval_requests.id")),
        sa.Column("proposed_action", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.Text(), nullable=False),
        sa.Column("confidence", sa.REAL()),
        sa.Column("reason", sa.Text()),
        sa.Column("requires_approval", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("llm_analysis_json", sa.Text()),
        sa.Column("correlation_id", sa.Text()),
        sa.Column("callback_url", sa.Text()),
        sa.Column("decision_note", sa.Text()),
        sa.Column("decided_by", sa.Text()),
        sa.Column("decided_at", sa.Text()),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.Column("expires_at", sa.Text()),
        if_not_exists=True,
    )
    _add_missing_columns(
        "approval_requests",
        {
            "callback_url": "ALTER TABLE approval_requests ADD COLUMN callback_url TEXT",
            "decision_note": "ALTER TABLE approval_requests ADD COLUMN decision_note TEXT",
            "decided_by": "ALTER TABLE approval_requests ADD COLUMN decided_by TEXT",
            "decided_at": "ALTER TABLE approval_requests ADD COLUMN decided_at TEXT",
        },
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_approval_requests_status "
        "ON approval_requests(status, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_approval_requests_source "
        "ON approval_requests(source, created_at)"
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("approval_requests.id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        timestamp_column("created_at"),
        if_not_exists=True,
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_events_request "
        "ON audit_events(request_id, created_at)"
    )

    op.create_table(
        "auto_approval_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source", sa.Text()),
        sa.Column("proposed_action", sa.Text()),
        sa.Column("conditions_json", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default=sa.text("1")),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        if_not_exists=True,
    )

    op.create_table(
        "permission_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("agent", sa.Text()),
        sa.Column("action", sa.Text()),
        sa.Column("resource", sa.Text()),
        sa.Column("conditions_json", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        if_not_exists=True,
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_permission_policies_enabled "
        "ON permission_policies(enabled, priority, id)"
    )

    op.create_table(
        "policy_check_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("permission_policies.id")),
        sa.Column("agent", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text()),
        sa.Column("context_json", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("requires_approval", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        timestamp_column("created_at"),
        if_not_exists=True,
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_policy_check_events_created "
        "ON policy_check_events(created_at)"
    )


def downgrade() -> None:
    op.drop_table("policy_check_events")
    op.drop_table("permission_policies")
    op.drop_table("auto_approval_rules")
    op.drop_table("audit_events")
    op.drop_table("approval_requests")


def _add_missing_columns(table_name: str, migrations: dict[str, str]) -> None:
    bind = op.get_bind()
    existing = {row[1] for row in bind.exec_driver_sql(f"PRAGMA table_info({table_name})")}
    for column_name, statement in migrations.items():
        if column_name not in existing:
            op.execute(statement)


def timestamp_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.Text(),
        nullable=False,
        server_default=sa.text("(datetime('now'))"),
    )
