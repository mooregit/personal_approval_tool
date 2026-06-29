from pat.database import Database
from pat.models import (
    AgentRegisterCreate,
    AgentUpdate,
    PermissionPolicyCreate,
    PermissionPolicyUpdate,
    PolicyCheckCreate,
)
from pat.repository import ApprovalRepository


def test_policy_check_matches_specific_policy_and_records_event(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)
    repo.register_agent(AgentRegisterCreate(agent="email-agent"))
    repo.update_agent("email-agent", AgentUpdate(status="active"))
    policy = repo.create_policy(
        PermissionPolicyCreate(
            name="External email requires approval",
            agent="email-agent",
            action="send_email",
            resource="gmail",
            conditions={"recipient_scope": "external"},
            decision="require_approval",
            risk_level="medium",
            priority=10,
        )
    )

    result = repo.check_policy(
        PolicyCheckCreate(
            agent="email-agent",
            action="send_email",
            resource="gmail",
            context={"recipient_scope": "external", "has_attachment": False},
        )
    )

    assert result == {
        "requires_approval": True,
        "decision": "require_approval",
        "approval_mode": "manual",
        "policy_id": policy["id"],
        "policy_name": "External email requires approval",
        "agent_status": "active",
        "requires_onboarding": False,
        "risk_level": "medium",
        "reason": "Matched policy: External email requires approval",
    }

    events = repo.list_policy_check_events()
    assert events[0]["policy_id"] == policy["id"]
    assert events[0]["requires_approval"] is True
    assert events[0]["context"]["recipient_scope"] == "external"


def test_policy_check_defaults_to_manual_approval_when_no_policy_matches(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)
    repo.register_agent(AgentRegisterCreate(agent="calendar-agent"))
    repo.update_agent("calendar-agent", AgentUpdate(status="active"))

    result = repo.check_policy(
        PolicyCheckCreate(
            agent="calendar-agent",
            action="create_event",
            resource="calendar",
            context={"invitees": 3},
        )
    )

    assert result["requires_approval"] is True
    assert result["decision"] == "require_approval"
    assert result["approval_mode"] == "manual"
    assert result["policy_id"] is None
    assert result["requires_onboarding"] is False
    assert result["reason"] == "No matching policy; defaulting to manual approval."


def test_policy_priority_chooses_first_matching_rule(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)
    repo.register_agent(AgentRegisterCreate(agent="email-agent"))
    repo.update_agent("email-agent", AgentUpdate(status="active"))
    repo.create_policy(
        PermissionPolicyCreate(
            name="Generic email approval",
            agent="email-agent",
            action="send_email",
            decision="require_approval",
            risk_level="medium",
            priority=100,
        )
    )
    auto_policy = repo.create_policy(
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

    assert result["policy_id"] == auto_policy["id"]
    assert result["decision"] == "auto_approve"
    assert result["requires_approval"] is False
    assert result["approval_mode"] == "auto"


def test_policy_update_and_delete(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)
    policy = repo.create_policy(
        PermissionPolicyCreate(
            name="Draft policy",
            action="save_memory",
            decision="require_approval",
        )
    )

    updated = repo.update_policy(
        policy["id"],
        PermissionPolicyUpdate(
            name="Memory writes are denied",
            decision="deny",
            risk_level="high",
            priority=1,
        ),
    )

    assert updated["name"] == "Memory writes are denied"
    assert updated["decision"] == "deny"
    assert updated["risk_level"] == "high"
    assert updated["priority"] == 1
    assert repo.delete_policy(policy["id"]) is True
    assert repo.get_policy(policy["id"]) is None
