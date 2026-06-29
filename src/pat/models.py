from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DecisionStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    edited = "edited"
    marked_wrong = "marked_wrong"
    expired = "expired"
    auto_approved = "auto_approved"
    cancelled = "cancelled"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"
    unknown = "unknown"


class PolicyDecision(StrEnum):
    allow = "allow"
    require_approval = "require_approval"
    deny = "deny"
    auto_approve = "auto_approve"
    log_only = "log_only"


class AgentStatus(StrEnum):
    new = "new"
    active = "active"
    suspended = "suspended"


class ApprovalRequestCreate(BaseModel):
    proposed_action: str = Field(min_length=1, max_length=200)
    source: str = Field(default="unknown", min_length=1, max_length=120)
    risk_level: RiskLevel = RiskLevel.unknown
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = Field(default=None, max_length=2000)
    requires_approval: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=160)
    callback_url: str | None = Field(default=None, max_length=1000)
    expires_at: str | None = None


class EmailIntakeCreate(BaseModel):
    from_address: str = Field(alias="from", min_length=1, max_length=320)
    to: str = Field(min_length=1, max_length=320)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    message_id: str | None = Field(default=None, max_length=500)
    thread_id: str | None = Field(default=None, max_length=500)
    action_hint: str | None = Field(default=None, max_length=200)
    risk_level: RiskLevel = RiskLevel.unknown
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = Field(default=None, max_length=2000)
    requires_approval: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

    def to_approval_request(self) -> ApprovalRequestCreate:
        email_metadata = {
            "intake_adapter": "email",
            "from": self.from_address,
            "to": self.to,
            "subject": self.subject,
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            **self.metadata,
        }
        return ApprovalRequestCreate(
            proposed_action=self.action_hint or "review_email_request",
            source="email",
            risk_level=self.risk_level,
            confidence=self.confidence,
            reason=self.reason or f"Email received from {self.from_address}: {self.subject}",
            requires_approval=self.requires_approval,
            payload={
                "from": self.from_address,
                "to": self.to,
                "subject": self.subject,
                "body": self.body,
            },
            metadata=email_metadata,
            correlation_id=self.message_id or self.thread_id,
        )


class DecisionCreate(BaseModel):
    status: DecisionStatus
    reviewer: str = Field(default="local-user", min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    edited_request: ApprovalRequestCreate | None = None


class ApprovalRequest(BaseModel):
    id: int
    parent_id: int | None
    proposed_action: str
    source: str
    risk_level: RiskLevel
    confidence: float | None
    reason: str | None
    requires_approval: bool
    status: DecisionStatus
    payload: dict[str, Any]
    metadata: dict[str, Any]
    llm_analysis: dict[str, Any] | None
    correlation_id: str | None
    callback_url: str | None
    decision_note: str | None
    decided_by: str | None
    decided_at: str | None
    created_at: str
    updated_at: str
    expires_at: str | None


class ApprovalResult(BaseModel):
    id: int
    status: DecisionStatus
    approved: bool
    terminal: bool
    action_to_execute: dict[str, Any] | None
    decision_note: str | None
    decided_by: str | None
    decided_at: str | None
    request: ApprovalRequest


class AuditEvent(BaseModel):
    id: int
    request_id: int
    event_type: str
    actor: str
    details: dict[str, Any]
    created_at: str


class PermissionPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    enabled: bool = True
    agent: str | None = Field(default=None, max_length=120)
    action: str | None = Field(default=None, max_length=200)
    resource: str | None = Field(default=None, max_length=200)
    conditions: dict[str, Any] = Field(default_factory=dict)
    decision: PolicyDecision
    risk_level: RiskLevel = RiskLevel.unknown
    priority: int = Field(default=100, ge=0, le=10000)


class PermissionPolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    enabled: bool | None = None
    agent: str | None = Field(default=None, max_length=120)
    action: str | None = Field(default=None, max_length=200)
    resource: str | None = Field(default=None, max_length=200)
    conditions: dict[str, Any] | None = None
    decision: PolicyDecision | None = None
    risk_level: RiskLevel | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)


class PermissionPolicy(BaseModel):
    id: int
    name: str
    description: str | None
    enabled: bool
    agent: str | None
    action: str | None
    resource: str | None
    conditions: dict[str, Any]
    decision: PolicyDecision
    risk_level: RiskLevel
    priority: int
    created_at: str
    updated_at: str


class AgentPermissionPolicy(BaseModel):
    policy: PermissionPolicy
    scope: str
    specificity: int


class AgentPermissions(BaseModel):
    agent: Agent
    policies: list[AgentPermissionPolicy]
    recent_checks: list[PolicyCheckEvent]


class PolicyCheckCreate(BaseModel):
    agent: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=200)
    resource: str | None = Field(default=None, max_length=200)
    context: dict[str, Any] = Field(default_factory=dict)


class PolicyCheckResult(BaseModel):
    requires_approval: bool
    decision: PolicyDecision
    approval_mode: str
    policy_id: int | None
    policy_name: str | None
    agent_status: AgentStatus
    requires_onboarding: bool
    risk_level: RiskLevel
    reason: str


class PolicyCheckEvent(BaseModel):
    id: int
    policy_id: int | None
    agent_status: AgentStatus | None
    agent: str
    action: str
    resource: str | None
    context: dict[str, Any]
    decision: PolicyDecision
    requires_approval: bool
    reason: str
    created_at: str


class AgentRegisterCreate(BaseModel):
    agent: str = Field(min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    callback_url: str | None = Field(default=None, max_length=1000)
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    status: AgentStatus | None = None
    callback_url: str | None = Field(default=None, max_length=1000)
    capabilities: list[str] | None = None
    metadata: dict[str, Any] | None = None


class Agent(BaseModel):
    id: int
    agent: str
    display_name: str | None
    description: str | None
    status: AgentStatus
    callback_url: str | None
    capabilities: list[str]
    metadata: dict[str, Any]
    first_seen_at: str
    last_seen_at: str
    created_at: str
    updated_at: str


class AgentRegistrationResult(BaseModel):
    agent: Agent
    requires_onboarding: bool
    message: str
