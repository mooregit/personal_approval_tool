from pat.models import EmailIntakeCreate


def test_email_intake_converts_to_approval_request():
    email = EmailIntakeCreate(
        from_address="agent@example.com",
        to="approval@example.com",
        subject="Approve follow-up email",
        body="Please review this proposed follow-up email.",
        message_id="email-123",
        thread_id="thread-456",
        action_hint="create_follow_up_email",
        risk_level="medium",
        confidence=0.82,
        metadata={"mailbox": "inbox"},
    )

    request = email.to_approval_request()

    assert request.proposed_action == "create_follow_up_email"
    assert request.source == "email"
    assert request.risk_level == "medium"
    assert request.confidence == 0.82
    assert request.correlation_id == "email-123"
    assert request.payload == {
        "from": "agent@example.com",
        "to": "approval@example.com",
        "subject": "Approve follow-up email",
        "body": "Please review this proposed follow-up email.",
    }
    assert request.metadata["intake_adapter"] == "email"
    assert request.metadata["thread_id"] == "thread-456"
    assert request.metadata["mailbox"] == "inbox"


def test_email_intake_accepts_from_alias():
    email = EmailIntakeCreate.model_validate(
        {
            "from": "agent@example.com",
            "to": "approval@example.com",
            "subject": "Needs review",
            "body": "Review this.",
        }
    )

    request = email.to_approval_request()

    assert request.proposed_action == "review_email_request"
    assert request.reason == "Email received from agent@example.com: Needs review"
