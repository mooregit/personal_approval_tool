from collections.abc import Generator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pat.callbacks import deliver_callback
from pat.config import Settings, get_settings
from pat.database import Database
from pat.models import (
    Agent,
    AgentPermissions,
    AgentRegisterCreate,
    AgentRegistrationResult,
    AgentUpdate,
    ApprovalRequest,
    ApprovalRequestCreate,
    ApprovalResult,
    AuditEvent,
    DecisionCreate,
    DecisionStatus,
    EmailIntakeCreate,
    PermissionPolicy,
    PermissionPolicyCreate,
    PermissionPolicyUpdate,
    PolicyCheckCreate,
    PolicyCheckEvent,
    PolicyCheckResult,
)
from pat.ollama import analyze_request
from pat.repository import ApprovalRepository

app = FastAPI(title="P.A.T. Personal Approval Tool", version="0.1.0")
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_db(settings: SettingsDep) -> Generator[Database, None, None]:
    db = Database(settings.database_path)
    db.init()
    yield db


DbDep = Annotated[Database, Depends(get_db)]


def get_repo(db: DbDep) -> ApprovalRepository:
    return ApprovalRepository(db)


RepoDep = Annotated[ApprovalRepository, Depends(get_repo)]
AuthorizationHeader = Annotated[str | None, Header()]
StatusQuery = Annotated[DecisionStatus | None, Query(alias="status")]


def require_api_key(
    settings: SettingsDep,
    authorization: AuthorizationHeader = None,
) -> None:
    expected = f"Bearer {settings.api_key}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid API key",
        )


@app.on_event("startup")
def startup() -> None:
    Database(get_settings().database_path).init()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health(settings: SettingsDep) -> dict[str, str | bool]:
    return {
        "status": "ok",
        "ollama_enabled": settings.enable_ollama,
        "ollama_model": settings.ollama_model,
    }


@app.post(
    "/api/agents/register",
    response_model=AgentRegistrationResult,
    dependencies=[Depends(require_api_key)],
)
def register_agent(
    registration: AgentRegisterCreate,
    repo: RepoDep,
) -> dict:
    return repo.register_agent(registration)


@app.get(
    "/api/agents",
    response_model=list[Agent],
    dependencies=[Depends(require_api_key)],
)
def list_agents(repo: RepoDep) -> list[dict]:
    return repo.list_agents()


@app.get(
    "/api/agents/{agent}",
    response_model=Agent,
    dependencies=[Depends(require_api_key)],
)
def get_agent(
    agent: str,
    repo: RepoDep,
) -> dict:
    agent_record = repo.get_agent(agent)
    if agent_record is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent_record


@app.patch(
    "/api/agents/{agent}",
    response_model=Agent,
    dependencies=[Depends(require_api_key)],
)
def update_agent(
    agent: str,
    update: AgentUpdate,
    repo: RepoDep,
) -> dict:
    agent_record = repo.update_agent(agent, update)
    if agent_record is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent_record


@app.get(
    "/api/agents/{agent}/permissions",
    response_model=AgentPermissions,
    dependencies=[Depends(require_api_key)],
)
def get_agent_permissions(
    agent: str,
    repo: RepoDep,
) -> dict:
    permissions = repo.get_agent_permissions(agent)
    if permissions is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return permissions


@app.get(
    "/api/agents/{agent}/policy-checks",
    response_model=list[PolicyCheckEvent],
    dependencies=[Depends(require_api_key)],
)
def list_agent_policy_check_events(
    agent: str,
    repo: RepoDep,
) -> list[dict]:
    if repo.get_agent(agent) is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return repo.list_policy_check_events(agent=agent)


@app.post(
    "/api/policy/check",
    response_model=PolicyCheckResult,
    dependencies=[Depends(require_api_key)],
)
def check_policy(
    check: PolicyCheckCreate,
    repo: RepoDep,
) -> dict:
    return repo.check_policy(check)


@app.get(
    "/api/policy/checks",
    response_model=list[PolicyCheckEvent],
    dependencies=[Depends(require_api_key)],
)
def list_policy_check_events(repo: RepoDep) -> list[dict]:
    return repo.list_policy_check_events()


@app.get(
    "/api/policies",
    response_model=list[PermissionPolicy],
    dependencies=[Depends(require_api_key)],
)
def list_policies(repo: RepoDep) -> list[dict]:
    return repo.list_policies()


@app.post(
    "/api/policies",
    response_model=PermissionPolicy,
    dependencies=[Depends(require_api_key)],
)
def create_policy(
    policy: PermissionPolicyCreate,
    repo: RepoDep,
) -> dict:
    return repo.create_policy(policy)


@app.get(
    "/api/policies/{policy_id}",
    response_model=PermissionPolicy,
    dependencies=[Depends(require_api_key)],
)
def get_policy(
    policy_id: int,
    repo: RepoDep,
) -> dict:
    policy = repo.get_policy(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="policy not found")
    return policy


@app.patch(
    "/api/policies/{policy_id}",
    response_model=PermissionPolicy,
    dependencies=[Depends(require_api_key)],
)
def update_policy(
    policy_id: int,
    update: PermissionPolicyUpdate,
    repo: RepoDep,
) -> dict:
    policy = repo.update_policy(policy_id, update)
    if policy is None:
        raise HTTPException(status_code=404, detail="policy not found")
    return policy


@app.delete(
    "/api/policies/{policy_id}",
    status_code=204,
    dependencies=[Depends(require_api_key)],
)
def delete_policy(
    policy_id: int,
    repo: RepoDep,
) -> None:
    deleted = repo.delete_policy(policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="policy not found")


@app.post(
    "/api/approval-requests",
    response_model=ApprovalRequest,
    dependencies=[Depends(require_api_key)],
)
async def create_approval_request(
    request: ApprovalRequestCreate,
    repo: RepoDep,
    settings: SettingsDep,
) -> dict:
    llm_analysis = await analyze_request(settings, request)
    return repo.create_request(request, llm_analysis=llm_analysis)


@app.post(
    "/api/email-intake",
    response_model=ApprovalRequest,
    dependencies=[Depends(require_api_key)],
)
async def create_email_intake_request(
    email: EmailIntakeCreate,
    repo: RepoDep,
    settings: SettingsDep,
) -> dict:
    request = email.to_approval_request()
    llm_analysis = await analyze_request(settings, request)
    return repo.create_request(request, llm_analysis=llm_analysis, actor="email-intake")


@app.get(
    "/api/approval-requests",
    response_model=list[ApprovalRequest],
    dependencies=[Depends(require_api_key)],
)
def list_approval_requests(
    repo: RepoDep,
    status_filter: StatusQuery = None,
) -> list[dict]:
    return repo.list_requests(status_filter)


@app.get(
    "/api/approval-requests/{request_id}",
    response_model=ApprovalRequest,
    dependencies=[Depends(require_api_key)],
)
def get_approval_request(
    request_id: int,
    repo: RepoDep,
) -> dict:
    request = repo.get_request(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    return request


@app.get(
    "/api/approval-requests/{request_id}/result",
    response_model=ApprovalResult,
    dependencies=[Depends(require_api_key)],
)
def get_approval_result(
    request_id: int,
    repo: RepoDep,
) -> dict:
    result = repo.get_result(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    return result


@app.post(
    "/api/approval-requests/{request_id}/decision",
    response_model=ApprovalRequest,
    dependencies=[Depends(require_api_key)],
)
async def decide_approval_request(
    request_id: int,
    decision: DecisionCreate,
    repo: RepoDep,
) -> dict:
    try:
        original = repo.get_request(request_id)
        if original is None:
            raise KeyError("approval request not found")
        updated = repo.decide(request_id, decision)
        result = repo.get_result(request_id)
        if result is not None and original["callback_url"]:
            callback_result = await deliver_callback(original["callback_url"], result)
            repo.record_callback_attempt(
                request_id,
                delivered=callback_result["delivered"],
                details=callback_result,
            )
        return updated
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/api/approval-requests/{request_id}/audit",
    response_model=list[AuditEvent],
    dependencies=[Depends(require_api_key)],
)
def list_audit_events(
    request_id: int,
    repo: RepoDep,
) -> list[dict]:
    return repo.list_audit_events(request_id)
