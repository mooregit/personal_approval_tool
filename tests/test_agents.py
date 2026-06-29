from pat.database import Database
from pat.models import (
    AgentRegisterCreate,
    AgentUpdate,
    PermissionPolicyCreate,
    PolicyCheckCreate,
)
from pat.repository import ApprovalRepository


def test_register_agent_starts_as_new(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)

    result = repo.register_agent(
        AgentRegisterCreate(
            agent="email-agent",
            display_name="Email Agent",
            description="Drafts and routes email approvals.",
            callback_url="http://127.0.0.1:9000/pat-callback",
            capabilities=["read_email", "send_email"],
        )
    )

    assert result["requires_onboarding"] is True
    assert result["agent"]["status"] == "new"
    assert result["agent"]["capabilities"] == ["read_email", "send_email"]


def test_unknown_agent_policy_check_auto_registers_and_requires_onboarding(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)

    result = repo.check_policy(
        PolicyCheckCreate(
            agent="unknown-agent",
            action="send_email",
            resource="gmail",
        )
    )

    agent = repo.get_agent("unknown-agent")
    assert agent is not None
    assert agent["status"] == "new"
    assert result["requires_approval"] is True
    assert result["requires_onboarding"] is True
    assert result["agent_status"] == "new"
    assert result["reason"] == "Agent is new and awaiting activation."


def test_active_agent_uses_matching_policy(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)
    repo.register_agent(AgentRegisterCreate(agent="email-agent"))
    repo.update_agent("email-agent", AgentUpdate(status="active"))
    policy = repo.create_policy(
        PermissionPolicyCreate(
            name="Internal email auto approval",
            agent="email-agent",
            action="send_email",
            conditions={"recipient_scope": "internal"},
            decision="auto_approve",
            risk_level="low",
            priority=10,
        )
    )

    result = repo.check_policy(
        PolicyCheckCreate(
            agent="email-agent",
            action="send_email",
            context={"recipient_scope": "internal"},
        )
    )

    assert result["policy_id"] == policy["id"]
    assert result["decision"] == "auto_approve"
    assert result["requires_approval"] is False
    assert result["agent_status"] == "active"
    assert result["requires_onboarding"] is False


def test_suspended_agent_is_denied_before_policy_match(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)
    repo.register_agent(AgentRegisterCreate(agent="email-agent"))
    repo.update_agent("email-agent", AgentUpdate(status="suspended"))
    repo.create_policy(
        PermissionPolicyCreate(
            name="Generic allow",
            agent="email-agent",
            action="send_email",
            decision="allow",
        )
    )

    result = repo.check_policy(
        PolicyCheckCreate(agent="email-agent", action="send_email")
    )

    assert result["decision"] == "deny"
    assert result["approval_mode"] == "blocked"
    assert result["requires_approval"] is False
    assert result["agent_status"] == "suspended"


def test_policy_check_events_record_agent_status(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)

    repo.check_policy(PolicyCheckCreate(agent="new-agent", action="save_memory"))

    events = repo.list_policy_check_events()
    assert events[0]["agent_status"] == "new"


def test_agent_permissions_include_global_and_agent_specific_policies(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)
    repo.register_agent(AgentRegisterCreate(agent="email-agent"))
    repo.update_agent("email-agent", AgentUpdate(status="active"))
    global_policy = repo.create_policy(
        PermissionPolicyCreate(
            name="External email approval",
            action="send_email",
            conditions={"recipient_scope": "external"},
            decision="require_approval",
            risk_level="medium",
            priority=20,
        )
    )
    agent_policy = repo.create_policy(
        PermissionPolicyCreate(
            name="Email agent internal auto approval",
            agent="email-agent",
            action="send_email",
            conditions={"recipient_scope": "internal"},
            decision="auto_approve",
            risk_level="low",
            priority=10,
        )
    )
    repo.create_policy(
        PermissionPolicyCreate(
            name="Calendar only policy",
            agent="calendar-agent",
            action="create_event",
            decision="require_approval",
        )
    )

    permissions = repo.get_agent_permissions("email-agent")

    policy_ids = [item["policy"]["id"] for item in permissions["policies"]]
    assert policy_ids == [agent_policy["id"], global_policy["id"]]
    assert permissions["policies"][0]["scope"] == "agent"
    assert permissions["policies"][0]["specificity"] == 3
    assert permissions["policies"][1]["scope"] == "global"
    assert permissions["policies"][1]["specificity"] == 2


def test_agent_permissions_include_agent_recent_checks_only(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)
    repo.register_agent(AgentRegisterCreate(agent="email-agent"))
    repo.update_agent("email-agent", AgentUpdate(status="active"))
    repo.register_agent(AgentRegisterCreate(agent="calendar-agent"))
    repo.update_agent("calendar-agent", AgentUpdate(status="active"))

    repo.check_policy(PolicyCheckCreate(agent="email-agent", action="send_email"))
    repo.check_policy(PolicyCheckCreate(agent="calendar-agent", action="create_event"))

    permissions = repo.get_agent_permissions("email-agent")

    assert len(permissions["recent_checks"]) == 1
    assert permissions["recent_checks"][0]["agent"] == "email-agent"
    assert permissions["recent_checks"][0]["action"] == "send_email"
