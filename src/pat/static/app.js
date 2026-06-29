const state = {
  requests: [],
  selected: null,
  apiKey: localStorage.getItem("pat_api_key") || "",
};

const apiKeyInput = document.querySelector("#apiKey");
const saveKeyButton = document.querySelector("#saveKey");
const statusFilter = document.querySelector("#statusFilter");
const queueList = document.querySelector("#queueList");
const detailPane = document.querySelector("#detailPane");
const selectedStatus = document.querySelector("#selectedStatus");
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
  return response.json();
}

async function loadQueue() {
  if (!state.apiKey) {
    queueList.innerHTML = '<div class="detail-pane empty">Enter and save your API key.</div>';
    return;
  }

  const status = statusFilter.value;
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  try {
    state.requests = await api(`/api/approval-requests${query}`);
    renderQueue();
  } catch (error) {
    queueList.innerHTML = `<div class="detail-pane empty">${error.message}</div>`;
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
    node.classList.toggle("active", state.selected?.id === request.id);
    node.querySelector(".request-title").textContent = request.proposed_action;
    node.querySelector(".request-meta").textContent =
      `${request.source} · ${request.risk_level} · ${request.status}`;
    node.addEventListener("click", () => selectRequest(request));
    queueList.append(node);
  }
}

function selectRequest(request) {
  state.selected = request;
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
    expires_at: request.expires_at,
  };
}

async function submitDecision(status) {
  const note = detailPane.querySelector("#note").value;
  const updated = await api(`/api/approval-requests/${state.selected.id}/decision`, {
    method: "POST",
    body: JSON.stringify({ status, note }),
  });
  state.selected = updated;
  await loadQueue();
  selectRequest(updated);
}

async function submitEdit() {
  const note = detailPane.querySelector("#note").value;
  const editedRequest = JSON.parse(detailPane.querySelector("#editPayload").value);
  const updated = await api(`/api/approval-requests/${state.selected.id}/decision`, {
    method: "POST",
    body: JSON.stringify({ status: "edited", note, edited_request: editedRequest }),
  });
  state.selected = updated;
  await loadQueue();
  selectRequest(updated);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

saveKeyButton.addEventListener("click", () => {
  state.apiKey = apiKeyInput.value;
  localStorage.setItem("pat_api_key", state.apiKey);
  loadQueue();
});

statusFilter.addEventListener("change", loadQueue);
setInterval(loadQueue, 15000);
loadQueue();
