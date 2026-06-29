"""Add agents registry.

Revision ID: 20260629_0002
Revises: 20260629_0001
Create Date: 2026-06-29
"""

import sqlalchemy as sa
from alembic import op

revision = "20260629_0002"
down_revision = "20260629_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("agent", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'new'")),
        sa.Column("callback_url", sa.Text()),
        sa.Column("capabilities_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        timestamp_column("first_seen_at"),
        timestamp_column("last_seen_at"),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        if_not_exists=True,
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_agent ON agents(agent)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status, last_seen_at)")
    _add_missing_columns(
        "policy_check_events",
        {
            "agent_status": "ALTER TABLE policy_check_events ADD COLUMN agent_status TEXT",
        },
    )


def downgrade() -> None:
    op.drop_table("agents")


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
