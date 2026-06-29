from pat.database import Database
from pat.models import ApprovalRequestCreate, DecisionCreate, DecisionStatus
from pat.repository import ApprovalRepository


def test_create_request_writes_audit_event(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)

    created = repo.create_request(
        ApprovalRequestCreate(
            proposed_action="create_follow_up_email",
            source="email-agent",
            risk_level="medium",
            confidence=0.82,
            reason="Interview occurred 5 days ago with no reply",
            payload={"to": "person@example.com"},
        ),
        llm_analysis={"summary": "Follow-up email draft."},
    )

    assert created["status"] == "pending"
    assert created["payload"] == {"to": "person@example.com"}

    events = repo.list_audit_events(created["id"])
    assert [event["event_type"] for event in events] == [
        "request.created",
        "request.llm_analyzed",
    ]


def test_edit_decision_preserves_original_and_creates_child(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)

    original = repo.create_request(
        ApprovalRequestCreate(
            proposed_action="create_calendar_event",
            source="calendar-agent",
            risk_level="high",
            payload={"title": "Interview"},
        ),
        llm_analysis=None,
    )

    edited = repo.decide(
        original["id"],
        DecisionCreate(
            status=DecisionStatus.edited,
            note="Change title",
            edited_request=ApprovalRequestCreate(
                proposed_action="create_calendar_event",
                source="calendar-agent",
                risk_level="medium",
                payload={"title": "Follow-up interview"},
            ),
        ),
    )

    original_after = repo.get_request(original["id"])
    assert original_after["status"] == "edited"
    assert original_after["payload"] == {"title": "Interview"}
    assert edited["parent_id"] == original["id"]
    assert edited["status"] == "pending"
    assert edited["payload"] == {"title": "Follow-up interview"}


def test_reject_updates_status_and_audit(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)

    created = repo.create_request(
        ApprovalRequestCreate(proposed_action="archive_email", source="email-agent"),
        llm_analysis=None,
    )

    rejected = repo.decide(
        created["id"],
        DecisionCreate(status=DecisionStatus.rejected, note="Wrong sender"),
    )

    assert rejected["status"] == "rejected"
    events = repo.list_audit_events(created["id"])
    assert events[-1]["event_type"] == "request.rejected"
    assert events[-1]["details"] == {"note": "Wrong sender"}


def test_result_is_pending_until_decision(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)

    created = repo.create_request(
        ApprovalRequestCreate(
            proposed_action="update_task",
            source="task-agent",
            payload={"task_id": "123"},
            callback_url="http://127.0.0.1:9000/pat-callback",
        ),
        llm_analysis=None,
    )

    result = repo.get_result(created["id"])

    assert result["status"] == "pending"
    assert result["approved"] is False
    assert result["terminal"] is False
    assert result["action_to_execute"] is None
    assert result["request"]["callback_url"] == "http://127.0.0.1:9000/pat-callback"


def test_result_includes_action_to_execute_after_approval(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)

    created = repo.create_request(
        ApprovalRequestCreate(
            proposed_action="update_task",
            source="task-agent",
            payload={"task_id": "123", "status": "done"},
            metadata={"workspace": "personal"},
        ),
        llm_analysis=None,
    )
    repo.decide(
        created["id"],
        DecisionCreate(status=DecisionStatus.approved, note="Looks correct"),
    )

    result = repo.get_result(created["id"])

    assert result["status"] == "approved"
    assert result["approved"] is True
    assert result["terminal"] is True
    assert result["decision_note"] == "Looks correct"
    assert result["decided_by"] == "local-user"
    assert result["decided_at"] is not None
    assert result["action_to_execute"] == {
        "proposed_action": "update_task",
        "source": "task-agent",
        "payload": {"task_id": "123", "status": "done"},
        "metadata": {"workspace": "personal"},
        "correlation_id": None,
        "callback_url": None,
    }


def test_result_rejected_is_terminal_without_action(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)

    created = repo.create_request(
        ApprovalRequestCreate(proposed_action="archive_email", source="email-agent"),
        llm_analysis=None,
    )
    repo.decide(
        created["id"],
        DecisionCreate(status=DecisionStatus.rejected, note="Do not archive"),
    )

    result = repo.get_result(created["id"])

    assert result["status"] == "rejected"
    assert result["approved"] is False
    assert result["terminal"] is True
    assert result["action_to_execute"] is None
