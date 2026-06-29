from typing import Any

from pat.database import (
    Database,
    json_dumps,
    row_to_agent,
    row_to_audit_event,
    row_to_policy,
    row_to_policy_check_event,
    row_to_request,
)
from pat.models import (
    AgentRegisterCreate,
    AgentStatus,
    AgentUpdate,
    ApprovalRequestCreate,
    DecisionCreate,
    DecisionStatus,
    PermissionPolicyCreate,
    PermissionPolicyUpdate,
    PolicyCheckCreate,
    PolicyDecision,
    RiskLevel,
)


class ApprovalRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_request(
        self,
        request: ApprovalRequestCreate,
        *,
        llm_analysis: dict[str, Any] | None,
        parent_id: int | None = None,
        actor: str = "agent",
    ) -> dict[str, Any]:
        status = DecisionStatus.pending
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO approval_requests (
                    parent_id, proposed_action, source, risk_level, confidence, reason,
                    requires_approval, status, payload_json, metadata_json, llm_analysis_json,
                    correlation_id, callback_url, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parent_id,
                    request.proposed_action,
                    request.source,
                    request.risk_level,
                    request.confidence,
                    request.reason,
                    int(request.requires_approval),
                    status,
                    json_dumps(request.payload),
                    json_dumps(request.metadata),
                    json_dumps(llm_analysis) if llm_analysis is not None else None,
                    request.correlation_id,
                    request.callback_url,
                    request.expires_at,
                ),
            )
            request_id = cursor.lastrowid
            self._insert_audit_event(
                conn,
                request_id=request_id,
                event_type="request.created",
                actor=actor,
                details={
                    "parent_id": parent_id,
                    "source": request.source,
                    "requires_approval": request.requires_approval,
                },
            )
            if llm_analysis is not None:
                self._insert_audit_event(
                    conn,
                    request_id=request_id,
                    event_type="request.llm_analyzed",
                    actor="ollama",
                    details=llm_analysis,
                )
            row = conn.execute(
                "SELECT * FROM approval_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
            return row_to_request(row)

    def list_requests(self, status: DecisionStatus | None = None) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            if status is None:
                rows = conn.execute(
                    "SELECT * FROM approval_requests ORDER BY created_at DESC, id DESC LIMIT 200"
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM approval_requests
                    WHERE status = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT 200
                    """,
                    (status,),
                ).fetchall()
            return [row_to_request(row) for row in rows]

    def get_request(self, request_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM approval_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
            return row_to_request(row) if row else None

    def decide(self, request_id: int, decision: DecisionCreate) -> dict[str, Any]:
        if decision.status == DecisionStatus.edited and decision.edited_request is None:
            raise ValueError("edited decisions require edited_request")
        if decision.status == DecisionStatus.pending:
            raise ValueError("cannot decide a request back to pending")

        with self.db.connect() as conn:
            current = conn.execute(
                "SELECT * FROM approval_requests WHERE id = ?", (request_id,)
            ).fetchone()
            if current is None:
                raise KeyError("approval request not found")

            conn.execute(
                """
                UPDATE approval_requests
                SET status = ?,
                    decision_note = ?,
                    decided_by = ?,
                    decided_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (decision.status, decision.note, decision.reviewer, request_id),
            )
            self._insert_audit_event(
                conn,
                request_id=request_id,
                event_type=f"request.{decision.status}",
                actor=decision.reviewer,
                details={"note": decision.note},
            )

        if decision.status == DecisionStatus.edited and decision.edited_request is not None:
            return self.create_request(
                decision.edited_request,
                llm_analysis=None,
                parent_id=request_id,
                actor=decision.reviewer,
            )

        updated = self.get_request(request_id)
        if updated is None:
            raise KeyError("approval request not found after decision")
        return updated

    def get_result(self, request_id: int) -> dict[str, Any] | None:
        request = self.get_request(request_id)
        if request is None:
            return None

        status = DecisionStatus(request["status"])
        approved = status in {DecisionStatus.approved, DecisionStatus.auto_approved}
        terminal = status != DecisionStatus.pending
        action_to_execute = None
        if approved:
            action_to_execute = {
                "proposed_action": request["proposed_action"],
                "source": request["source"],
                "payload": request["payload"],
                "metadata": request["metadata"],
                "correlation_id": request["correlation_id"],
                "callback_url": request["callback_url"],
            }

        return {
            "id": request["id"],
            "status": status,
            "approved": approved,
            "terminal": terminal,
            "action_to_execute": action_to_execute,
            "decision_note": request["decision_note"],
            "decided_by": request["decided_by"],
            "decided_at": request["decided_at"],
            "request": request,
        }

    def list_audit_events(self, request_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_events
                WHERE request_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (request_id,),
            ).fetchall()
            return [row_to_audit_event(row) for row in rows]

    def record_callback_attempt(
        self,
        request_id: int,
        *,
        delivered: bool,
        details: dict[str, Any],
    ) -> None:
        with self.db.connect() as conn:
            self._insert_audit_event(
                conn,
                request_id=request_id,
                event_type="callback.delivered" if delivered else "callback.failed",
                actor="pat",
                details=details,
            )

    def register_agent(self, registration: AgentRegisterCreate) -> dict[str, Any]:
        existing = self.get_agent(registration.agent)
        if existing is not None:
            update = AgentUpdate(
                display_name=registration.display_name,
                description=registration.description,
                callback_url=registration.callback_url,
                capabilities=registration.capabilities,
                metadata=registration.metadata,
            )
            agent = self.update_agent(registration.agent, update)
            if agent is None:
                raise KeyError("agent not found after registration update")
            return {
                "agent": agent,
                "requires_onboarding": agent["status"] == AgentStatus.new,
                "message": "Agent registration updated.",
            }

        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agents (
                    agent, display_name, description, status, callback_url,
                    capabilities_json, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    registration.agent,
                    registration.display_name,
                    registration.description,
                    AgentStatus.new,
                    registration.callback_url,
                    json_dumps(registration.capabilities),
                    json_dumps(registration.metadata),
                ),
            )
            row = conn.execute("SELECT * FROM agents WHERE id = ?", (cursor.lastrowid,)).fetchone()
            agent = row_to_agent(row)
        return {
            "agent": agent,
            "requires_onboarding": True,
            "message": "Agent registered and awaiting activation.",
        }

    def list_agents(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM agents
                ORDER BY
                    CASE status
                        WHEN 'new' THEN 0
                        WHEN 'active' THEN 1
                        WHEN 'suspended' THEN 2
                        ELSE 3
                    END,
                    last_seen_at DESC,
                    agent ASC
                """
            ).fetchall()
            return [row_to_agent(row) for row in rows]

    def get_agent(self, agent: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM agents WHERE agent = ?", (agent,)).fetchone()
            return row_to_agent(row) if row else None

    def update_agent(self, agent: str, update: AgentUpdate) -> dict[str, Any] | None:
        current = self.get_agent(agent)
        if current is None:
            return None

        data = update.model_dump(exclude_unset=True)
        if not data:
            self.touch_agent(agent)
            return self.get_agent(agent)

        assignments = []
        values = []
        column_map = {
            "display_name": "display_name",
            "description": "description",
            "status": "status",
            "callback_url": "callback_url",
            "capabilities": "capabilities_json",
            "metadata": "metadata_json",
        }
        for field, value in data.items():
            assignments.append(f"{column_map[field]} = ?")
            if field in {"capabilities", "metadata"}:
                values.append(json_dumps(value))
            else:
                values.append(value)

        assignments.append("updated_at = datetime('now')")
        values.append(agent)
        with self.db.connect() as conn:
            conn.execute(
                f"""
                UPDATE agents
                SET {", ".join(assignments)}
                WHERE agent = ?
                """,
                tuple(values),
            )
            row = conn.execute("SELECT * FROM agents WHERE agent = ?", (agent,)).fetchone()
            return row_to_agent(row)

    def touch_agent(self, agent: str) -> dict[str, Any]:
        existing = self.get_agent(agent)
        if existing is None:
            registration = self.register_agent(AgentRegisterCreate(agent=agent))
            return registration["agent"]

        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE agents
                SET last_seen_at = datetime('now'), updated_at = datetime('now')
                WHERE agent = ?
                """,
                (agent,),
            )
            row = conn.execute("SELECT * FROM agents WHERE agent = ?", (agent,)).fetchone()
            return row_to_agent(row)

    def get_agent_permissions(self, agent: str) -> dict[str, Any] | None:
        agent_record = self.get_agent(agent)
        if agent_record is None:
            return None

        return {
            "agent": agent_record,
            "policies": self.list_applicable_policies(agent),
            "recent_checks": self.list_policy_check_events(agent=agent),
        }

    def create_policy(self, policy: PermissionPolicyCreate) -> dict[str, Any]:
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO permission_policies (
                    name, description, enabled, agent, action, resource, conditions_json,
                    decision, risk_level, priority
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy.name,
                    policy.description,
                    int(policy.enabled),
                    policy.agent,
                    policy.action,
                    policy.resource,
                    json_dumps(policy.conditions),
                    policy.decision,
                    policy.risk_level,
                    policy.priority,
                ),
            )
            row = conn.execute(
                "SELECT * FROM permission_policies WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return row_to_policy(row)

    def list_policies(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM permission_policies
                ORDER BY enabled DESC, priority ASC, id ASC
                """
            ).fetchall()
            return [row_to_policy(row) for row in rows]

    def list_applicable_policies(self, agent: str) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM permission_policies
                WHERE enabled = 1
                  AND (agent IS NULL OR agent = ?)
                ORDER BY priority ASC, agent IS NOT NULL DESC, id ASC
                """,
                (agent,),
            ).fetchall()

        policies = []
        for row in rows:
            policy = row_to_policy(row)
            scope = "agent" if policy["agent"] == agent else "global"
            specificity = self._policy_specificity(policy)
            policies.append(
                {
                    "policy": policy,
                    "scope": scope,
                    "specificity": specificity,
                }
            )
        return policies

    def get_policy(self, policy_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM permission_policies WHERE id = ?",
                (policy_id,),
            ).fetchone()
            return row_to_policy(row) if row else None

    def update_policy(
        self,
        policy_id: int,
        update: PermissionPolicyUpdate,
    ) -> dict[str, Any] | None:
        current = self.get_policy(policy_id)
        if current is None:
            return None

        data = update.model_dump(exclude_unset=True)
        if not data:
            return current

        assignments = []
        values = []
        column_map = {
            "name": "name",
            "description": "description",
            "enabled": "enabled",
            "agent": "agent",
            "action": "action",
            "resource": "resource",
            "conditions": "conditions_json",
            "decision": "decision",
            "risk_level": "risk_level",
            "priority": "priority",
        }
        for field, value in data.items():
            assignments.append(f"{column_map[field]} = ?")
            if field == "conditions":
                values.append(json_dumps(value))
            elif field == "enabled":
                values.append(int(value))
            else:
                values.append(value)

        assignments.append("updated_at = datetime('now')")
        values.append(policy_id)
        with self.db.connect() as conn:
            conn.execute(
                f"""
                UPDATE permission_policies
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                tuple(values),
            )
            row = conn.execute(
                "SELECT * FROM permission_policies WHERE id = ?",
                (policy_id,),
            ).fetchone()
            return row_to_policy(row)

    def delete_policy(self, policy_id: int) -> bool:
        with self.db.connect() as conn:
            cursor = conn.execute("DELETE FROM permission_policies WHERE id = ?", (policy_id,))
            return cursor.rowcount > 0

    def check_policy(self, check: PolicyCheckCreate) -> dict[str, Any]:
        agent = self.touch_agent(check.agent)
        agent_status = AgentStatus(agent["status"])
        if agent_status == AgentStatus.suspended:
            result = {
                "requires_approval": False,
                "decision": PolicyDecision.deny,
                "approval_mode": "blocked",
                "policy_id": None,
                "policy_name": None,
                "agent_status": agent_status,
                "requires_onboarding": False,
                "risk_level": RiskLevel.high,
                "reason": "Agent is suspended.",
            }
            self._record_policy_check(check, result)
            return result

        if agent_status == AgentStatus.new:
            result = {
                "requires_approval": True,
                "decision": PolicyDecision.require_approval,
                "approval_mode": "manual",
                "policy_id": None,
                "policy_name": None,
                "agent_status": agent_status,
                "requires_onboarding": True,
                "risk_level": RiskLevel.unknown,
                "reason": "Agent is new and awaiting activation.",
            }
            self._record_policy_check(check, result)
            return result

        policy = self._find_matching_policy(check)
        if policy is None:
            result = {
                "requires_approval": True,
                "decision": PolicyDecision.require_approval,
                "approval_mode": "manual",
                "policy_id": None,
                "policy_name": None,
                "agent_status": agent_status,
                "requires_onboarding": False,
                "risk_level": RiskLevel.unknown,
                "reason": "No matching policy; defaulting to manual approval.",
            }
        else:
            decision = PolicyDecision(policy["decision"])
            result = {
                "requires_approval": decision == PolicyDecision.require_approval,
                "decision": decision,
                "approval_mode": self._approval_mode(decision),
                "policy_id": policy["id"],
                "policy_name": policy["name"],
                "agent_status": agent_status,
                "requires_onboarding": False,
                "risk_level": RiskLevel(policy["risk_level"]),
                "reason": f"Matched policy: {policy['name']}",
            }
            if decision == PolicyDecision.auto_approve:
                result["requires_approval"] = False
            elif decision == PolicyDecision.deny:
                result["requires_approval"] = False

        self._record_policy_check(check, result)
        return result

    def list_policy_check_events(self, agent: str | None = None) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            if agent is None:
                rows = conn.execute(
                    """
                    SELECT * FROM policy_check_events
                    ORDER BY created_at DESC, id DESC
                    LIMIT 200
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM policy_check_events
                    WHERE agent = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT 200
                    """,
                    (agent,),
                ).fetchall()
            return [row_to_policy_check_event(row) for row in rows]

    def _find_matching_policy(self, check: PolicyCheckCreate) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM permission_policies
                WHERE enabled = 1
                ORDER BY priority ASC, id ASC
                """
            ).fetchall()

        for row in rows:
            policy = row_to_policy(row)
            if policy["agent"] is not None and policy["agent"] != check.agent:
                continue
            if policy["action"] is not None and policy["action"] != check.action:
                continue
            if policy["resource"] is not None and policy["resource"] != check.resource:
                continue
            if not self._conditions_match(policy["conditions"], check.context):
                continue
            return policy
        return None

    @staticmethod
    def _conditions_match(conditions: dict[str, Any], context: dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            if context.get(key) != expected:
                return False
        return True

    @staticmethod
    def _policy_specificity(policy: dict[str, Any]) -> int:
        score = 0
        for field in ("agent", "action", "resource"):
            if policy[field] is not None:
                score += 1
        score += len(policy["conditions"])
        return score

    @staticmethod
    def _approval_mode(decision: PolicyDecision) -> str:
        if decision == PolicyDecision.require_approval:
            return "manual"
        if decision == PolicyDecision.auto_approve:
            return "auto"
        if decision == PolicyDecision.deny:
            return "blocked"
        return "none"

    def _record_policy_check(
        self,
        check: PolicyCheckCreate,
        result: dict[str, Any],
    ) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO policy_check_events (
                    policy_id, agent_status, agent, action, resource, context_json, decision,
                    requires_approval, reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["policy_id"],
                    result["agent_status"],
                    check.agent,
                    check.action,
                    check.resource,
                    json_dumps(check.context),
                    result["decision"],
                    int(result["requires_approval"]),
                    result["reason"],
                ),
            )

    @staticmethod
    def _insert_audit_event(
        conn,
        *,
        request_id: int,
        event_type: str,
        actor: str,
        details: Any,
    ) -> None:
        conn.execute(
            """
            INSERT INTO audit_events (request_id, event_type, actor, details_json)
            VALUES (?, ?, ?, ?)
            """,
            (request_id, event_type, actor, json_dumps(details)),
        )
