from pat.callbacks import build_callback_payload
from pat.database import Database
from pat.models import ApprovalRequestCreate, DecisionCreate, DecisionStatus
from pat.repository import ApprovalRepository


def test_callback_payload_matches_result_contract(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)
    created = repo.create_request(
        ApprovalRequestCreate(
            proposed_action="update_task",
            source="test-agent",
            payload={"task_id": "123"},
            callback_url="http://127.0.0.1:9000/pat-callback",
        ),
        llm_analysis=None,
    )
    repo.decide(
        created["id"],
        DecisionCreate(status=DecisionStatus.approved, note="Looks correct"),
    )

    payload = build_callback_payload(repo.get_result(created["id"]))

    assert payload["id"] == created["id"]
    assert payload["status"] == "approved"
    assert payload["approved"] is True
    assert payload["terminal"] is True
    assert payload["decision_note"] == "Looks correct"
    assert payload["action_to_execute"]["payload"] == {"task_id": "123"}


def test_callback_attempts_are_recorded_in_audit(tmp_path):
    db = Database(str(tmp_path / "pat.sqlite3"))
    db.init()
    repo = ApprovalRepository(db)
    created = repo.create_request(
        ApprovalRequestCreate(
            proposed_action="archive_email",
            source="test-agent",
            callback_url="http://127.0.0.1:9000/pat-callback",
        ),
        llm_analysis=None,
    )

    repo.record_callback_attempt(
        created["id"],
        delivered=False,
        details={
            "delivered": False,
            "url": "http://127.0.0.1:9000/pat-callback",
            "error": "connection refused",
        },
    )

    events = repo.list_audit_events(created["id"])
    assert events[-1]["event_type"] == "callback.failed"
    assert events[-1]["details"] == {
        "delivered": False,
        "error": "connection refused",
        "url": "http://127.0.0.1:9000/pat-callback",
    }
