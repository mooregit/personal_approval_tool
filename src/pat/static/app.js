const state = {
  activeView: "approvals",
  requests: [],
  agents: [],
  policies: [],
  checks: [],
  selectedRequest: null,
  selectedAgent: null,
  apiKey: localStorage.getItem("pat_api_key") || "",
};

const apiKeyInput = document.querySelector("#apiKey");
const saveKeyButton = document.querySelector("#saveKey");
const tabs = document.querySelectorAll("[data-view]");
const views = document.querySelectorAll(".view");
const statusFilter = document.querySelector("#statusFilter");
const queueList = document.querySelector("#queueList");
const detailPane = document.querySelector("#detailPane");
const selectedStatus = document.querySelector("#selectedStatus");
const agentsList = document.querySelector("#agentsList");
const agentDetail = document.querySelector("#agentDetail");
const agentStatus = document.querySelector("#agentStatus");
const policiesList = document.querySelector("#policiesList");
const policyForm = document.querySelector("#policyForm");
const policyMode = document.querySelector("#policyMode");
const auditList = document.querySelector("#auditList");
const template = document.querySelector("#requestTemplate");

apiKeyInput.value = state.apiKey;

function headers() {
  return {
    Authorization: `Bearer ${state.apiKey}`,
    "Content-Type": "application/json",
  };
}

function formatJson(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...headers(), ...(options.headers || {}) },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || response.statusText);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function requireKey(target) {
  if (state.apiKey) {
    return true;
  }
  target.innerHTML = '<div class="detail-pane empty">Enter and save your API key.</div>';
  return false;
}

async function loadActiveView() {
  if (state.activeView === "approvals") {
    await loadQueue();
  } else if (state.activeView === "agents") {
    await loadAgents();
  } else if (state.activeView === "policies") {
    await loadPolicies();
  } else if (state.activeView === "audit") {
    await loadAudit();
  }
}

function setView(view) {
  state.activeView = view;
  tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.view === view));
  views.forEach((section) => section.classList.toggle("active", section.id === `${view}View`));
  loadActiveView();
}

async function loadQueue() {
  if (!requireKey(queueList)) {
    return;
  }

  const status = statusFilter.value;
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  try {
    state.requests = await api(`/api/approval-requests${query}`);
    renderQueue();
  } catch (error) {
    queueList.innerHTML = `<div class="detail-pane empty">${escapeHtml(error.message)}</div>`;
  }
}

function renderQueue() {
  queueList.innerHTML = "";
  if (state.requests.length === 0) {
    queueList.innerHTML = '<div class="detail-pane empty">No requests found.</div>';
    return;
  }

  for (const request of state.requests) {
    const node = template.content.firstElementChild.cloneNode(true);
    node.classList.toggle("active", state.selectedRequest?.id === request.id);
    node.querySelector(".request-title").textContent = request.proposed_action;
    node.querySelector(".request-meta").textContent =
      `${request.source} · ${request.risk_level} · ${request.status}`;
    node.addEventListener("click", () => selectRequest(request));
    queueList.append(node);
  }
}

function selectRequest(request) {
  state.selectedRequest = request;
  selectedStatus.textContent = request.status;
  selectedStatus.className = `badge risk-${request.risk_level}`;
  renderQueue();
  renderDetail(request);
}

function renderDetail(request) {
  const analysis = request.llm_analysis || {};
  detailPane.className = "detail-pane";
  detailPane.innerHTML = `
    <dl class="field-grid">
      <dt>Action</dt><dd>${escapeHtml(request.proposed_action)}</dd>
      <dt>Source</dt><dd>${escapeHtml(request.source)}</dd>
      <dt>Risk</dt><dd class="risk-${request.risk_level}">${escapeHtml(request.risk_level)}</dd>
      <dt>Confidence</dt><dd>${request.confidence ?? "not provided"}</dd>
      <dt>Reason</dt><dd>${escapeHtml(request.reason || "not provided")}</dd>
      <dt>Created</dt><dd>${escapeHtml(request.created_at)}</dd>
    </dl>

    <div class="analysis">
      <strong>Ollama analysis</strong>
      <p>${escapeHtml(analysis.summary || "No model analysis available.")}</p>
      <p>${escapeHtml(analysis.risk_review || "")}</p>
      <p><strong>Suggested:</strong> ${escapeHtml(analysis.suggested_decision || "inspect")}</p>
    </div>

    <div class="actions">
      <button class="primary" data-decision="approved">Approve</button>
      <button class="danger" data-decision="rejected">Reject</button>
      <button data-decision="marked_wrong">Mark wrong</button>
      <button data-decision="cancelled">Cancel</button>
      <button data-show-edit="true">Edit as new</button>
    </div>

    <label for="note"><strong>Decision note</strong></label>
    <textarea id="note" placeholder="Optional note"></textarea>

    <div id="editBox" hidden>
      <label for="editPayload"><strong>Edited request JSON</strong></label>
      <textarea id="editPayload">${escapeHtml(formatJson(toEditableRequest(request)))}</textarea>
      <button class="primary" id="submitEdit" type="button">Submit edited request</button>
    </div>

    <h3>Payload</h3>
    <pre>${escapeHtml(formatJson(request.payload))}</pre>
    <h3>Metadata</h3>
    <pre>${escapeHtml(formatJson(request.metadata))}</pre>
  `;

  detailPane.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", () => submitDecision(button.dataset.decision));
  });
  detailPane.querySelector("[data-show-edit]").addEventListener("click", () => {
    detailPane.querySelector("#editBox").hidden = false;
  });
  detailPane.querySelector("#submitEdit").addEventListener("click", submitEdit);
}

function toEditableRequest(request) {
  return {
    proposed_action: request.proposed_action,
    source: request.source,
    risk_level: request.risk_level,
    confidence: request.confidence,
    reason: request.reason,
    requires_approval: request.requires_approval,
    payload: request.payload,
    metadata: request.metadata,
    correlation_id: request.correlation_id,
    callback_url: request.callback_url,
    expires_at: request.expires_at,
  };
}

async function submitDecision(status) {
  const note = detailPane.querySelector("#note").value;
  const updated = await api(`/api/approval-requests/${state.selectedRequest.id}/decision`, {
    method: "POST",
    body: JSON.stringify({ status, note }),
  });
  state.selectedRequest = updated;
  await loadQueue();
  selectRequest(updated);
}

async function submitEdit() {
  const note = detailPane.querySelector("#note").value;
  const editedRequest = JSON.parse(detailPane.querySelector("#editPayload").value);
  const updated = await api(`/api/approval-requests/${state.selectedRequest.id}/decision`, {
    method: "POST",
    body: JSON.stringify({ status: "edited", note, edited_request: editedRequest }),
  });
  state.selectedRequest = updated;
  await loadQueue();
  selectRequest(updated);
}

async function loadAgents() {
  if (!requireKey(agentsList)) {
    return;
  }
  try {
    state.agents = await api("/api/agents");
    renderAgents();
  } catch (error) {
    agentsList.innerHTML = `<div class="detail-pane empty">${escapeHtml(error.message)}</div>`;
  }
}

function renderAgents() {
  if (state.agents.length === 0) {
    agentsList.innerHTML = '<div class="detail-pane empty">No agents registered yet.</div>';
    return;
  }
  agentsList.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Agent</th>
          <th>Status</th>
          <th>Capabilities</th>
          <th>Last seen</th>
        </tr>
      </thead>
      <tbody>
        ${state.agents
          .map(
            (agent) => `
              <tr class="selectable" data-agent="${escapeHtml(agent.agent)}">
                <td>
                  <strong>${escapeHtml(agent.display_name || agent.agent)}</strong>
                  <span>${escapeHtml(agent.agent)}</span>
                </td>
                <td>${statusBadge(agent.status)}</td>
                <td>${escapeHtml(agent.capabilities.join(", ") || "none declared")}</td>
                <td>${escapeHtml(agent.last_seen_at)}</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
  agentsList.querySelectorAll("[data-agent]").forEach((row) => {
    row.addEventListener("click", () => selectAgent(row.dataset.agent));
  });
}

async function selectAgent(agentName) {
  const permissions = await api(`/api/agents/${encodeURIComponent(agentName)}/permissions`);
  state.selectedAgent = permissions.agent;
  agentStatus.textContent = permissions.agent.status;
  agentStatus.className = `badge status-${permissions.agent.status}`;
  renderAgentDetail(permissions);
}

function renderAgentDetail(permissions) {
  const agent = permissions.agent;
  agentDetail.className = "detail-pane";
  agentDetail.innerHTML = `
    <dl class="field-grid">
      <dt>Name</dt><dd>${escapeHtml(agent.display_name || agent.agent)}</dd>
      <dt>ID</dt><dd>${escapeHtml(agent.agent)}</dd>
      <dt>Status</dt><dd>${statusBadge(agent.status)}</dd>
      <dt>Capabilities</dt><dd>${escapeHtml(agent.capabilities.join(", ") || "none declared")}</dd>
      <dt>First seen</dt><dd>${escapeHtml(agent.first_seen_at)}</dd>
      <dt>Last seen</dt><dd>${escapeHtml(agent.last_seen_at)}</dd>
    </dl>
    <div class="actions">
      <button class="primary" data-agent-status="active">Activate</button>
      <button data-agent-status="new">Mark new</button>
      <button class="danger" data-agent-status="suspended">Suspend</button>
    </div>
    <h3>Effective policies</h3>
    ${renderPolicySummaryTable(permissions.policies)}
    <h3>Recent checks</h3>
    ${renderChecksTable(permissions.recent_checks)}
    <h3>Metadata</h3>
    <pre>${escapeHtml(formatJson(agent.metadata))}</pre>
  `;
  agentDetail.querySelectorAll("[data-agent-status]").forEach((button) => {
    button.addEventListener("click", async () => {
      await updateAgentStatus(agent.agent, button.dataset.agentStatus);
    });
  });
}

async function updateAgentStatus(agent, status) {
  await api(`/api/agents/${encodeURIComponent(agent)}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
  await loadAgents();
  await selectAgent(agent);
}

async function loadPolicies() {
  if (!requireKey(policiesList)) {
    return;
  }
  try {
    state.policies = await api("/api/policies");
    renderPolicies();
  } catch (error) {
    policiesList.innerHTML = `<div class="detail-pane empty">${escapeHtml(error.message)}</div>`;
  }
}

function renderPolicies() {
  if (state.policies.length === 0) {
    policiesList.innerHTML = '<div class="detail-pane empty">No policies defined yet.</div>';
    return;
  }
  policiesList.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Policy</th>
          <th>Scope</th>
          <th>Decision</th>
          <th>Priority</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${state.policies
          .map(
            (policy) => `
              <tr>
                <td>
                  <strong>${escapeHtml(policy.name)}</strong>
                  <span>${escapeHtml(policy.action || "any action")} · ${escapeHtml(
                    policy.resource || "any resource"
                  )}</span>
                </td>
                <td>${escapeHtml(policy.agent || "global")}</td>
                <td>${decisionBadge(policy.decision)} ${policy.enabled ? "" : statusBadge("disabled")}</td>
                <td>${policy.priority}</td>
                <td class="row-actions">
                  <button data-edit-policy="${policy.id}" type="button">Edit</button>
                  <button data-toggle-policy="${policy.id}" type="button">${
                    policy.enabled ? "Disable" : "Enable"
                  }</button>
                  <button class="danger" data-delete-policy="${policy.id}" type="button">Delete</button>
                </td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
  policiesList.querySelectorAll("[data-edit-policy]").forEach((button) => {
    button.addEventListener("click", () => editPolicy(Number(button.dataset.editPolicy)));
  });
  policiesList.querySelectorAll("[data-toggle-policy]").forEach((button) => {
    button.addEventListener("click", () => togglePolicy(Number(button.dataset.togglePolicy)));
  });
  policiesList.querySelectorAll("[data-delete-policy]").forEach((button) => {
    button.addEventListener("click", () => deletePolicy(Number(button.dataset.deletePolicy)));
  });
}

function editPolicy(id) {
  const policy = state.policies.find((item) => item.id === id);
  if (!policy) {
    return;
  }
  policyMode.textContent = `Edit #${policy.id}`;
  document.querySelector("#policyId").value = policy.id;
  document.querySelector("#policyName").value = policy.name;
  document.querySelector("#policyDescription").value = policy.description || "";
  document.querySelector("#policyAgent").value = policy.agent || "";
  document.querySelector("#policyAction").value = policy.action || "";
  document.querySelector("#policyResource").value = policy.resource || "";
  document.querySelector("#policyDecision").value = policy.decision;
  document.querySelector("#policyRisk").value = policy.risk_level;
  document.querySelector("#policyPriority").value = policy.priority;
  document.querySelector("#policyEnabled").checked = policy.enabled;
  document.querySelector("#policyConditions").value = formatJson(policy.conditions);
}

async function togglePolicy(id) {
  const policy = state.policies.find((item) => item.id === id);
  await api(`/api/policies/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled: !policy.enabled }),
  });
  await loadPolicies();
}

async function deletePolicy(id) {
  await api(`/api/policies/${id}`, { method: "DELETE" });
  resetPolicyForm();
  await loadPolicies();
}

async function savePolicy(event) {
  event.preventDefault();
  let conditions;
  try {
    conditions = JSON.parse(document.querySelector("#policyConditions").value || "{}");
  } catch {
    alert("Conditions must be valid JSON.");
    return;
  }

  const id = document.querySelector("#policyId").value;
  const body = {
    name: document.querySelector("#policyName").value,
    description: blankToNull(document.querySelector("#policyDescription").value),
    enabled: document.querySelector("#policyEnabled").checked,
    agent: blankToNull(document.querySelector("#policyAgent").value),
    action: blankToNull(document.querySelector("#policyAction").value),
    resource: blankToNull(document.querySelector("#policyResource").value),
    conditions,
    decision: document.querySelector("#policyDecision").value,
    risk_level: document.querySelector("#policyRisk").value,
    priority: Number(document.querySelector("#policyPriority").value || 100),
  };

  if (id) {
    await api(`/api/policies/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  } else {
    await api("/api/policies", { method: "POST", body: JSON.stringify(body) });
  }
  resetPolicyForm();
  await loadPolicies();
}

function resetPolicyForm() {
  policyMode.textContent = "Create";
  policyForm.reset();
  document.querySelector("#policyId").value = "";
  document.querySelector("#policyPriority").value = "100";
  document.querySelector("#policyEnabled").checked = true;
  document.querySelector("#policyConditions").value = "{}";
}

async function loadAudit() {
  if (!requireKey(auditList)) {
    return;
  }
  try {
    state.checks = await api("/api/policy/checks");
    auditList.innerHTML = renderChecksTable(state.checks);
  } catch (error) {
    auditList.innerHTML = `<div class="detail-pane empty">${escapeHtml(error.message)}</div>`;
  }
}

function renderPolicySummaryTable(policies) {
  if (policies.length === 0) {
    return '<p class="empty">No enabled policies apply to this agent.</p>';
  }
  return `
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Scope</th>
          <th>Decision</th>
          <th>Priority</th>
        </tr>
      </thead>
      <tbody>
        ${policies
          .map(
            (item) => `
              <tr>
                <td>
                  <strong>${escapeHtml(item.policy.name)}</strong>
                  <span>${escapeHtml(item.policy.action || "any action")}</span>
                </td>
                <td>${escapeHtml(item.scope)} · ${item.specificity}</td>
                <td>${decisionBadge(item.policy.decision)}</td>
                <td>${item.policy.priority}</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderChecksTable(checks) {
  if (checks.length === 0) {
    return '<div class="detail-pane empty">No policy checks found.</div>';
  }
  return `
    <table>
      <thead>
        <tr>
          <th>When</th>
          <th>Agent</th>
          <th>Action</th>
          <th>Decision</th>
          <th>Reason</th>
        </tr>
      </thead>
      <tbody>
        ${checks
          .map(
            (check) => `
              <tr>
                <td>${escapeHtml(check.created_at)}</td>
                <td>
                  <strong>${escapeHtml(check.agent)}</strong>
                  <span>${escapeHtml(check.agent_status || "unknown")}</span>
                </td>
                <td>
                  ${escapeHtml(check.action)}
                  <span>${escapeHtml(check.resource || "any resource")}</span>
                </td>
                <td>${decisionBadge(check.decision)}</td>
                <td>${escapeHtml(check.reason)}</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function statusBadge(status) {
  return `<span class="badge status-${escapeHtml(status)}">${escapeHtml(status)}</span>`;
}

function decisionBadge(decision) {
  return `<span class="badge decision-${escapeHtml(decision)}">${escapeHtml(decision)}</span>`;
}

function blankToNull(value) {
  const trimmed = value.trim();
  return trimmed.length === 0 ? null : trimmed;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => setView(tab.dataset.view));
});

saveKeyButton.addEventListener("click", () => {
  state.apiKey = apiKeyInput.value;
  localStorage.setItem("pat_api_key", state.apiKey);
  loadActiveView();
});

statusFilter.addEventListener("change", loadQueue);
document.querySelector("#refreshAgents").addEventListener("click", loadAgents);
document.querySelector("#refreshPolicies").addEventListener("click", loadPolicies);
document.querySelector("#refreshAudit").addEventListener("click", loadAudit);
document.querySelector("#resetPolicyForm").addEventListener("click", resetPolicyForm);
policyForm.addEventListener("submit", savePolicy);

setInterval(() => {
  if (state.activeView === "approvals") {
    loadQueue();
  }
}, 15000);

loadActiveView();
