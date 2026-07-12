(function () {
  const form = document.getElementById("job-form");
  const apiKeyInput = document.getElementById("api-key");
  const sourceInput = document.getElementById("source");
  const drivingInput = document.getElementById("driving");
  const consentInput = document.getElementById("consent_confirmed");
  const submitButton = document.getElementById("submit");
  const statusText = document.getElementById("status");
  const details = document.getElementById("details");
  const jobSummary = document.getElementById("job-summary");
  const jobSummaryContent = document.getElementById("job-summary-content");
  const retryJobButton = document.getElementById("retry-job");
  const clearResultButton = document.getElementById("clear-result");
  const completionPanel = document.getElementById("completion-panel");
  const completionTitle = document.getElementById("completion-title");
  const completionMessage = document.getElementById("completion-message");
  const preview = document.getElementById("preview");
  const emptyState = document.getElementById("empty-state");
  const downloadLink = document.getElementById("download");
  const auditDownloadLink = document.getElementById("download-audit");
  const health = document.getElementById("health");
  const authHint = document.getElementById("auth-hint");
  const uploadLimits = document.getElementById("upload-limits");
  const formErrors = document.getElementById("form-errors");
  const sourceSummary = document.getElementById("source-summary");
  const drivingSummary = document.getElementById("driving-summary");
  const jobsList = document.getElementById("jobs-list");
  const jobStatusFilter = document.getElementById("job-status-filter");
  const authorizationStatusFilter = document.getElementById("authorization-status-filter");
  const authorizationReferenceFilter = document.getElementById("authorization-reference-filter");
  const ownerFilterField = document.getElementById("owner-filter-field");
  const ownerIdFilter = document.getElementById("owner-id-filter");
  const refreshJobsButton = document.getElementById("refresh-jobs");
  const exportAuthorizationRecordButton = document.getElementById("export-authorization-record");
  const accessPanel = document.getElementById("access-panel");
  const accessIdentity = document.getElementById("access-identity");
  const apiKeyForm = document.getElementById("api-key-form");
  const newKeyOwnerInput = document.getElementById("new-key-owner");
  const newKeyLabelInput = document.getElementById("new-key-label");
  const newKeyRoleInput = document.getElementById("new-key-role");
  const createApiKeyButton = document.getElementById("create-api-key");
  const newApiKeyResult = document.getElementById("new-api-key-result");
  const apiKeysList = document.getElementById("api-keys-list");
  const refreshApiKeysButton = document.getElementById("refresh-api-keys");
  const cleanupRunsList = document.getElementById("cleanup-runs-list");
  const cleanupPanel = document.getElementById("cleanup-panel");
  const cleanupOlderThanDaysInput = document.getElementById("cleanup-older-than-days");
  const cleanupDryRunButton = document.getElementById("cleanup-dry-run");
  const cleanupDeleteButton = document.getElementById("cleanup-delete");
  const refreshCleanupRunsButton = document.getElementById("refresh-cleanup-runs");
  const operationsAuditPanel = document.getElementById("operations-audit-panel");
  const operationsAuditList = document.getElementById("operations-audit-list");
  const operationsAuditActionFilter = document.getElementById("operations-audit-action-filter");
  const exportOperationsAuditButton = document.getElementById("export-operations-audit");
  const refreshOperationsAuditButton = document.getElementById("refresh-operations-audit");
  const sourceRules = {
    label: "Source image",
    extensions: [".jpg", ".jpeg", ".png"],
    types: ["image/jpeg", "image/jpg", "image/png"],
  };
  const drivingRules = {
    label: "Driving file",
    extensions: [".jpg", ".jpeg", ".png", ".mp4", ".pkl"],
    types: [
      "image/jpeg",
      "image/jpg",
      "image/png",
      "video/mp4",
      "application/octet-stream",
      "application/pickle",
      "application/x-pickle",
      "",
    ],
  };
  let currentResultUrl = null;
  let currentAuditUrl = null;
  let currentAuthorizationExportUrl = null;
  let currentOperationsAuditExportUrl = null;
  let maxUploadBytes = null;
  let currentJobId = null;
  let pendingSubmissionKey = null;
  let currentAccessProfile = null;

  apiKeyInput.value = sessionStorage.getItem("liveportrait_api_key") || "";
  updateAuthHint();
  apiKeyInput.addEventListener("change", () => {
    sessionStorage.setItem("liveportrait_api_key", apiKeyInput.value.trim());
    updateAuthHint();
    loadAccessProfile();
    loadJobs();
  });

  renderEmptyState();
  checkHealth();
  loadJobs();
  loadAccessProfile();
  form.addEventListener("submit", createJob);
  sourceInput.addEventListener("change", () => {
    pendingSubmissionKey = null;
    renderFileSummary(sourceInput, sourceSummary);
    clearFormErrors();
  });
  drivingInput.addEventListener("change", () => {
    pendingSubmissionKey = null;
    renderFileSummary(drivingInput, drivingSummary);
    clearFormErrors();
  });
  consentInput.addEventListener("change", clearFormErrors);
  jobStatusFilter.addEventListener("change", loadJobs);
  authorizationStatusFilter.addEventListener("change", loadJobs);
  authorizationReferenceFilter.addEventListener("change", loadJobs);
  ownerIdFilter.addEventListener("change", loadJobs);
  refreshJobsButton.addEventListener("click", loadJobs);
  exportAuthorizationRecordButton.addEventListener("click", exportAuthorizationRecord);
  apiKeyForm.addEventListener("submit", createManagedApiKey);
  refreshApiKeysButton.addEventListener("click", loadApiKeys);
  cleanupDryRunButton.addEventListener("click", () => runCleanup(true));
  cleanupDeleteButton.addEventListener("click", () => runCleanup(false));
  refreshCleanupRunsButton.addEventListener("click", loadCleanupRuns);
  operationsAuditActionFilter.addEventListener("change", loadOperationsAuditEvents);
  exportOperationsAuditButton.addEventListener("click", exportOperationsAuditEvents);
  refreshOperationsAuditButton.addEventListener("click", loadOperationsAuditEvents);
  clearResultButton.addEventListener("click", clearCurrentJob);
  retryJobButton.addEventListener("click", retryCurrentJob);

  async function createJob(event) {
    event.preventDefault();
    resetResult();
    completionPanel.hidden = true;
    clearFormErrors();

    const errors = validateJobForm();
    if (errors.length) {
      showFormErrors(errors);
      setStatus("Needs attention");
      return;
    }

    try {
      submitButton.disabled = true;
      setStatus("Uploading");
      pendingSubmissionKey = pendingSubmissionKey || createIdempotencyKey();
      const body = new FormData(form);
      body.delete("api-key");
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: {
          ...authHeaders(),
          "x-idempotency-key": pendingSubmissionKey,
        },
        body,
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(friendlyError(response.status, payload.detail || "Upload failed"));
      }
      pendingSubmissionKey = null;
      renderJobSummary(payload);
      details.textContent = "Job " + payload.job_id;
      await loadJobs();
      await pollJob(payload.job_id);
    } catch (error) {
      setStatus("Failed");
      details.textContent = error.message;
      submitButton.disabled = false;
    }
  }

  async function pollJob(jobId) {
    const response = await fetch("/api/jobs/" + encodeURIComponent(jobId), {
      headers: authHeaders(),
    });
    const payload = await readJson(response);
    if (!response.ok) {
      throw new Error(payload.detail || "Status check failed");
    }

    setStatus(payload.status);
    renderJobSummary(payload);
    details.textContent = "Job " + payload.job_id + " updated at " + payload.updated_at;

    if (payload.status === "succeeded") {
      await loadResult(jobId);
      await loadAuditExport(jobId);
      renderCompletion(payload);
      await loadJobs();
      submitButton.disabled = false;
      return;
    }

    if (payload.status === "failed") {
      completionPanel.hidden = true;
      details.textContent = payload.error_message || "Generation failed";
      await loadJobs();
      submitButton.disabled = false;
      return;
    }

    window.setTimeout(() => pollJob(jobId).catch(showError), 2000);
  }

  async function loadResult(jobId) {
    const response = await fetch("/api/jobs/" + encodeURIComponent(jobId) + "/result", {
      headers: authHeaders(),
    });
    if (!response.ok) {
      const payload = await readJson(response);
      throw new Error(payload.detail || "Result download failed");
    }

    const blob = await response.blob();
    if (currentResultUrl) {
      URL.revokeObjectURL(currentResultUrl);
    }
    currentResultUrl = URL.createObjectURL(blob);
    renderPreview(blob, currentResultUrl);
    downloadLink.href = currentResultUrl;
    downloadLink.download = "liveportrait-result-" + jobId;
    downloadLink.hidden = false;
  }

  async function loadAuditExport(jobId) {
    const response = await fetch("/api/jobs/" + encodeURIComponent(jobId) + "/export", {
      headers: authHeaders(),
    });
    const payload = await readJson(response);
    if (!response.ok) {
      throw new Error(payload.detail || "Audit export failed");
    }

    if (currentAuditUrl) {
      URL.revokeObjectURL(currentAuditUrl);
    }
    currentAuditUrl = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    }));
    auditDownloadLink.href = currentAuditUrl;
    auditDownloadLink.download = "liveportrait-audit-" + jobId + ".json";
    auditDownloadLink.hidden = false;
  }

  async function loadJobs() {
    try {
      const query = new URLSearchParams({ limit: "10" });
      const status = jobStatusFilter.value;
      const authorizationStatus = authorizationStatusFilter.value;
      const authorizationReference = authorizationReferenceFilter.value.trim();
      const ownerId = ownerIdFilter.value.trim();
      if (status) {
        query.set("status", status);
      }
      if (authorizationStatus) {
        query.set("authorization_status", authorizationStatus);
      }
      if (authorizationReference) {
        query.set("authorization_reference", authorizationReference);
      }
      if (currentAccessProfile && currentAccessProfile.is_admin && ownerId) {
        query.set("owner_id", ownerId);
      }
      const url = "/api/jobs?" + query.toString();
      const response = await fetch(url, {
        headers: authHeaders(),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "Could not load recent jobs");
      }
      renderJobs(payload.jobs || []);
    } catch (error) {
      jobsList.textContent = error.message;
    }
  }

  async function loadCleanupRuns() {
    try {
      const response = await fetch("/api/cleanup-runs?limit=5", {
        headers: authHeaders(),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "Could not load cleanup records");
      }
      renderCleanupRuns(payload.records || []);
    } catch (error) {
      cleanupRunsList.textContent = error.message;
    }
  }

  async function loadAccessProfile() {
    try {
      const response = await fetch("/api/whoami", { headers: authHeaders() });
      const payload = await readJson(response);
      if (!response.ok) {
        currentAccessProfile = null;
        ownerFilterField.hidden = true;
        accessPanel.hidden = true;
        cleanupPanel.hidden = true;
        operationsAuditPanel.hidden = true;
        return;
      }
      currentAccessProfile = payload;
      accessIdentity.textContent = "Signed in as " + payload.owner_id + " (" + payload.role + ").";
      ownerFilterField.hidden = !payload.is_admin;
      if (!payload.is_admin) {
        ownerIdFilter.value = "";
      }
      accessPanel.hidden = !payload.is_admin;
      cleanupPanel.hidden = !payload.is_admin;
      operationsAuditPanel.hidden = !payload.is_admin;
      if (payload.is_admin) {
        await loadApiKeys();
        await loadCleanupRuns();
        await loadOperationsAuditEvents();
      }
    } catch (_) {
      currentAccessProfile = null;
      ownerFilterField.hidden = true;
      accessPanel.hidden = true;
      cleanupPanel.hidden = true;
      operationsAuditPanel.hidden = true;
    }
  }

  async function loadApiKeys() {
    try {
      const response = await fetch("/api/admin/api-keys", {
        headers: authHeaders(),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "Could not load API keys");
      }
      renderApiKeys(payload.api_keys || []);
    } catch (error) {
      apiKeysList.textContent = error.message;
    }
  }

  async function createManagedApiKey(event) {
    event.preventDefault();
    const ownerId = newKeyOwnerInput.value.trim();
    if (!ownerId) {
      newApiKeyResult.hidden = false;
      newApiKeyResult.textContent = "Owner is required before issuing a key.";
      return;
    }

    try {
      createApiKeyButton.disabled = true;
      const response = await fetch("/api/admin/api-keys", {
        method: "POST",
        headers: {
          ...authHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          owner_id: ownerId,
          label: newKeyLabelInput.value.trim() || null,
          role: newKeyRoleInput.value,
        }),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "API key creation failed");
      }
      renderNewApiKey(payload);
      apiKeyForm.reset();
      newKeyRoleInput.value = "user";
      await loadApiKeys();
      await loadOperationsAuditEvents();
    } catch (error) {
      newApiKeyResult.hidden = false;
      newApiKeyResult.textContent = error.message;
    } finally {
      createApiKeyButton.disabled = false;
    }
  }

  function renderNewApiKey(payload) {
    newApiKeyResult.hidden = false;
    newApiKeyResult.replaceChildren();
    const label = document.createElement("span");
    label.textContent = "New key for " + payload.owner_id + " - copy it now:";
    const secret = document.createElement("code");
    secret.textContent = payload.api_key;
    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "secondary-button";
    copyButton.textContent = "Copy";
    copyButton.addEventListener("click", async () => {
      await copyText(payload.api_key);
      details.textContent = "New API key copied.";
    });
    newApiKeyResult.append(label, secret, copyButton);
  }

  function renderApiKeys(records) {
    apiKeysList.replaceChildren();
    if (!records.length) {
      apiKeysList.textContent = "No managed API keys.";
      return;
    }

    for (const record of records) {
      const item = document.createElement("div");
      item.className = "api-key-row";
      const main = document.createElement("span");
      main.className = "job-main";
      main.textContent = record.owner_id + " - " + record.role;
      const meta = document.createElement("span");
      meta.className = "job-meta";
      meta.textContent = [
        record.label || "No label",
        "prefix " + record.key_prefix,
        "created " + formatTime(record.created_at),
        record.revoked_at ? "revoked " + formatTime(record.revoked_at) : "active",
      ].join(" | ");
      const revoke = document.createElement("button");
      revoke.type = "button";
      revoke.className = "secondary-button danger-button";
      revoke.textContent = "Revoke";
      revoke.disabled = Boolean(record.revoked_at) || record.status === "revoked";
      revoke.addEventListener("click", () => revokeApiKey(record));
      item.append(main, meta, revoke);
      apiKeysList.appendChild(item);
    }
  }

  async function revokeApiKey(record) {
    if (!window.confirm("Revoke API key for " + record.owner_id + "?")) {
      return;
    }

    try {
      const response = await fetch("/api/admin/api-keys/" + encodeURIComponent(record.key_id) + "/revoke", {
        method: "POST",
        headers: authHeaders(),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "API key revoke failed");
      }
      details.textContent = "Revoked API key for " + payload.owner_id + ".";
      await loadApiKeys();
      await loadOperationsAuditEvents();
    } catch (error) {
      details.textContent = error.message;
    }
  }

  async function loadOperationsAuditEvents() {
    try {
      const query = new URLSearchParams({ limit: "20" });
      const action = operationsAuditActionFilter.value.trim();
      if (action) {
        query.set("action", action);
      }
      const response = await fetch("/api/admin/audit-events?" + query.toString(), {
        headers: authHeaders(),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "Could not load operation records");
      }
      renderOperationsAuditEvents(payload.events || []);
    } catch (error) {
      operationsAuditList.textContent = error.message;
    }
  }

  function renderOperationsAuditEvents(events) {
    operationsAuditList.replaceChildren();
    if (!events.length) {
      operationsAuditList.textContent = "No operation records.";
      return;
    }

    for (const event of events) {
      const item = document.createElement("div");
      item.className = "operation-row";
      const main = document.createElement("span");
      main.className = "job-main";
      main.textContent = event.action + " - " + (event.target_type || "target");
      const meta = document.createElement("span");
      meta.className = "job-meta";
      meta.textContent = [
        "actor " + (event.actor_owner_id || "unknown"),
        event.target_id ? "target " + shortHash(event.target_id) : "no target id",
        formatTime(event.created_at),
      ].join(" | ");
      const metadata = document.createElement("span");
      metadata.className = "job-meta";
      metadata.textContent = summarizeMetadata(event.metadata);
      item.append(main, meta, metadata);
      operationsAuditList.appendChild(item);
    }
  }

  async function exportOperationsAuditEvents() {
    try {
      exportOperationsAuditButton.disabled = true;
      const query = new URLSearchParams({ limit: "200" });
      const action = operationsAuditActionFilter.value.trim();
      if (action) {
        query.set("action", action);
      }
      const response = await fetch("/api/admin/audit-events/export?" + query.toString(), {
        headers: authHeaders(),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "Operations audit export failed");
      }
      if (currentOperationsAuditExportUrl) {
        URL.revokeObjectURL(currentOperationsAuditExportUrl);
      }
      currentOperationsAuditExportUrl = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      }));
      const suffix = safeDownloadName(action || "all");
      const link = document.createElement("a");
      link.href = currentOperationsAuditExportUrl;
      link.download = "liveportrait-operations-audit-" + suffix + ".json";
      link.click();
      details.textContent = "Operations audit export downloaded.";
    } catch (error) {
      details.textContent = error.message;
    } finally {
      exportOperationsAuditButton.disabled = false;
    }
  }

  async function runCleanup(dryRun) {
    const olderThanDays = Number(cleanupOlderThanDaysInput.value);
    if (!Number.isInteger(olderThanDays) || olderThanDays < 1) {
      cleanupRunsList.textContent = "Cleanup days must be at least 1.";
      return;
    }
    if (!dryRun && !window.confirm("Delete old succeeded/failed job files and database rows?")) {
      return;
    }

    try {
      cleanupDryRunButton.disabled = true;
      cleanupDeleteButton.disabled = true;
      const response = await fetch("/api/cleanup-runs", {
        method: "POST",
        headers: {
          ...authHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          older_than_days: olderThanDays,
          dry_run: dryRun,
          confirm_delete: !dryRun,
        }),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "Cleanup request failed");
      }
      details.textContent = [
        dryRun ? "Cleanup dry run" : "Cleanup completed",
        ": matched ",
        payload.matched_jobs,
        ", deleted ",
        payload.deleted_jobs,
        ", audit events ",
        payload.operational_audit_deleted_events,
        "/",
        payload.operational_audit_matched_events,
        ", freed ",
        formatBytes(payload.removed_bytes),
        ".",
      ].join("");
      await loadCleanupRuns();
      await loadJobs();
      await loadOperationsAuditEvents();
    } catch (error) {
      details.textContent = error.message;
    } finally {
      cleanupDryRunButton.disabled = false;
      cleanupDeleteButton.disabled = false;
    }
  }

  function renderCleanupRuns(records) {
    cleanupRunsList.replaceChildren();
    if (!records.length) {
      cleanupRunsList.textContent = "No cleanup records.";
      return;
    }

    for (const record of records) {
      const item = document.createElement("div");
      item.className = "cleanup-row";
      item.innerHTML = [
        '<span class="job-main">',
        escapeHtml(formatTime(record.created_at)),
        record.dry_run ? " - dry run" : " - cleaned",
        "</span>",
        '<span class="job-meta">',
        "matched ",
        escapeHtml(record.matched_jobs || 0),
        ", deleted ",
        escapeHtml(record.deleted_jobs || 0),
        ", active skipped ",
        escapeHtml(record.skipped_active_jobs || 0),
        ", audit events ",
        escapeHtml(record.operational_audit_deleted_events || 0),
        "/",
        escapeHtml(record.operational_audit_matched_events || 0),
        ", freed ",
        escapeHtml(formatBytes(record.removed_bytes || 0)),
        "</span>",
      ].join("");
      cleanupRunsList.appendChild(item);
    }
  }

  function renderJobs(jobs) {
    jobsList.replaceChildren();
    if (!jobs.length) {
      jobsList.textContent = hasJobFilters() ? "No jobs match the current filters." : "No recent jobs.";
      return;
    }

    for (const job of jobs) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "job-row";
      item.innerHTML = [
        '<span class="job-main">',
        escapeHtml(job.source_filename || "source"),
        " -> ",
        escapeHtml(job.driving_filename || "driving"),
        "</span>",
        '<span class="job-meta">',
        '<span class="status-chip" data-status="',
        escapeHtml(job.status),
        '">',
        escapeHtml(job.status),
        "</span>",
        " ",
        escapeHtml(currentAccessProfile && currentAccessProfile.is_admin ? "owner " + (job.owner_id || "unknown") : ""),
        " ",
        escapeHtml(job.authorization_reference || "No auth ref"),
        " ",
        escapeHtml(formatTime(job.updated_at)),
        "</span>",
      ].join("");
      item.addEventListener("click", () => selectJob(job));
      jobsList.appendChild(item);
    }
  }

  async function selectJob(job) {
    setStatus(job.status);
    resetResult();
    renderJobSummary(job);
    details.textContent = "Job " + job.job_id + " updated at " + job.updated_at;
    if (job.status === "failed") {
      completionPanel.hidden = true;
      details.textContent = job.error_message || "Generation failed";
      return;
    }
    if (job.status === "succeeded") {
      await loadResult(job.job_id);
      await loadAuditExport(job.job_id);
      renderCompletion(job);
    }
  }

  async function retryCurrentJob() {
    if (!currentJobId) {
      return;
    }
    try {
      retryJobButton.disabled = true;
      const response = await fetch("/api/jobs/" + encodeURIComponent(currentJobId) + "/retry", {
        method: "POST",
        headers: authHeaders(),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "Retry request failed");
      }
      completionPanel.hidden = true;
      setStatus(payload.status);
      renderJobSummary(payload);
      details.textContent = "Job " + payload.job_id + " queued for retry.";
      await loadJobs();
      await loadOperationsAuditEvents();
      await pollJob(payload.job_id);
    } catch (error) {
      details.textContent = error.message;
    } finally {
      retryJobButton.disabled = false;
    }
  }

  async function exportAuthorizationRecord() {
    const authorizationReference = authorizationReferenceFilter.value.trim();
    if (!authorizationReference) {
      jobsList.textContent = "Enter an authorization reference before exporting.";
      return;
    }

    try {
      exportAuthorizationRecordButton.disabled = true;
      const response = await fetch(
        "/api/authorization-records/export?authorization_reference=" + encodeURIComponent(authorizationReference),
        { headers: authHeaders() },
      );
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "Authorization export failed");
      }
      if (currentAuthorizationExportUrl) {
        URL.revokeObjectURL(currentAuthorizationExportUrl);
      }
      currentAuthorizationExportUrl = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      }));
      const link = document.createElement("a");
      link.href = currentAuthorizationExportUrl;
      link.download = "liveportrait-authorization-" + safeDownloadName(authorizationReference) + ".json";
      link.click();
      details.textContent = "Authorization export downloaded for " + authorizationReference + ".";
    } catch (error) {
      details.textContent = error.message;
    } finally {
      exportAuthorizationRecordButton.disabled = false;
    }
  }

  function updateAuthHint() {
    if (apiKeyInput.value.trim()) {
      authHint.textContent = "Personal access key is kept only for this browser session and sent with job requests.";
      authHint.dataset.state = "ready";
      return;
    }
    authHint.textContent = "Local testing may not require a key. Deployed services usually do.";
    authHint.dataset.state = "neutral";
  }

  function renderJobSummary(job) {
    currentJobId = job.job_id || null;
    retryJobButton.hidden = job.status !== "failed";
    jobSummary.hidden = false;
    jobSummaryContent.replaceChildren(
      summaryRow("Status", job.status || "unknown"),
      summaryRow("Job ID", job.job_id || "unknown"),
      summaryRow("Attempts", String(job.attempt_count || 0)),
      summaryRow("Files", (job.source_filename || "source") + " -> " + (job.driving_filename || "driving")),
      summaryRow("Created", formatTime(job.created_at)),
      summaryRow("Updated", formatTime(job.updated_at)),
      summaryRow("Source SHA", shortHash(job.source_sha256)),
      summaryRow("Driving SHA", shortHash(job.driving_sha256)),
      summaryRow("Auth basis", job.authorization_basis || "Not specified"),
      summaryRow("Auth ref", job.authorization_reference || "Not specified"),
      summaryRow("Reviewer", job.authorization_reviewer || "Not specified"),
      summaryRow("Review", job.authorization_status || "self_confirmed"),
      summaryRow("Owner", job.owner_id || "unknown"),
    );

    if (job.output_sha256) {
      jobSummaryContent.appendChild(summaryRow("Output SHA", shortHash(job.output_sha256)));
    }
    if (job.error_message) {
      jobSummaryContent.appendChild(summaryRow("Failure", job.error_message));
    }
  }

  function summaryRow(label, value) {
    const fragment = document.createDocumentFragment();
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value || "Not available";
    fragment.append(term, description);
    return fragment;
  }

  function clearCurrentJob() {
    resetResult();
    jobSummary.hidden = true;
    jobSummaryContent.replaceChildren();
    currentJobId = null;
    retryJobButton.hidden = true;
    completionPanel.hidden = true;
    setStatus("Ready");
    details.textContent = "No job selected.";
  }

  function renderPreview(blob, url) {
    preview.replaceChildren();
    if (blob.type.startsWith("video/")) {
      const video = document.createElement("video");
      video.src = url;
      video.controls = true;
      video.playsInline = true;
      preview.appendChild(video);
      return;
    }

    const image = document.createElement("img");
    image.src = url;
    image.alt = "Generated result";
    preview.appendChild(image);
  }

  function renderEmptyState() {
    preview.replaceChildren(emptyState);
    emptyState.hidden = false;
  }

  function renderCompletion(job) {
    completionPanel.hidden = false;
    completionTitle.textContent = "Result ready";
    completionMessage.textContent = "Job " + shortHash(job.job_id) + " finished. Download the result or audit JSON below.";
  }

  async function checkHealth() {
    try {
      const response = await fetch("/api/health");
      const payload = await readJson(response);
      health.textContent = response.ok ? "Online" : "Offline";
      health.dataset.state = response.ok ? "ok" : "bad";
      if (response.ok) {
        maxUploadBytes = Number(payload.max_upload_bytes) || null;
        uploadLimits.textContent = "Max upload " + formatBytes(payload.max_upload_bytes) + " per file; queue limit " + payload.max_active_jobs + " active jobs.";
      }
    } catch (error) {
      health.textContent = "Offline";
      health.dataset.state = "bad";
      uploadLimits.textContent = "Upload limits unavailable while the API is offline.";
    }
  }

  function validateJobForm() {
    const errors = [];
    errors.push(...validateSelectedFile(sourceInput, sourceRules));
    errors.push(...validateSelectedFile(drivingInput, drivingRules));
    if (!consentInput.checked) {
      errors.push("Confirm source image authorization before generating.");
    }
    return errors;
  }

  function validateSelectedFile(input, rules) {
    const file = input.files && input.files[0];
    if (!file) {
      return [rules.label + " is required."];
    }

    const suffix = "." + file.name.split(".").pop().toLowerCase();
    const errors = [];
    if (!rules.extensions.includes(suffix)) {
      errors.push("Unsupported " + rules.label.toLowerCase() + " type: " + suffix + ".");
    }

    const fileType = (file.type || "").toLowerCase();
    if (fileType && !rules.types.includes(fileType)) {
      errors.push(rules.label + " content type is not supported: " + fileType + ".");
    }

    if (maxUploadBytes && file.size > maxUploadBytes) {
      errors.push(rules.label + " is larger than " + formatBytes(maxUploadBytes) + ".");
    }
    return errors;
  }

  function renderFileSummary(input, target) {
    const file = input.files && input.files[0];
    if (!file) {
      target.textContent = "No file selected";
      return;
    }
    target.textContent = file.name + " - " + formatBytes(file.size);
  }

  function showFormErrors(errors) {
    formErrors.hidden = false;
    const list = document.createElement("ul");
    for (const error of errors) {
      const item = document.createElement("li");
      item.textContent = error;
      list.appendChild(item);
    }
    formErrors.replaceChildren(list);
    details.textContent = errors[0];
  }

  function clearFormErrors() {
    formErrors.hidden = true;
    formErrors.replaceChildren();
  }

  function friendlyError(status, detail) {
    if (status === 429) {
      return "The job queue is full. Try again after existing jobs finish.";
    }
    if (status === 413) {
      return "One of the files is larger than the upload limit.";
    }
    return detail;
  }

  function authHeaders() {
    const key = apiKeyInput.value.trim();
    return key ? { "x-api-key": key } : {};
  }

  function hasJobFilters() {
    return Boolean(
      jobStatusFilter.value ||
      authorizationStatusFilter.value ||
      authorizationReferenceFilter.value.trim() ||
      (currentAccessProfile && currentAccessProfile.is_admin && ownerIdFilter.value.trim()),
    );
  }

  async function copyText(value) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(value);
      return;
    }
    const helper = document.createElement("textarea");
    helper.value = value;
    helper.setAttribute("readonly", "");
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    document.execCommand("copy");
    helper.remove();
  }

  function safeDownloadName(value) {
    return String(value || "record").replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^_+|_+$/g, "") || "record";
  }

  function createIdempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "web-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
  }

  async function readJson(response) {
    try {
      return await response.json();
    } catch (error) {
      return {};
    }
  }

  function resetResult() {
    if (currentResultUrl) {
      URL.revokeObjectURL(currentResultUrl);
      currentResultUrl = null;
    }
    preview.replaceChildren();
    renderEmptyState();
    downloadLink.hidden = true;
    downloadLink.removeAttribute("href");
    auditDownloadLink.hidden = true;
    auditDownloadLink.removeAttribute("href");
    if (currentAuditUrl) {
      URL.revokeObjectURL(currentAuditUrl);
      currentAuditUrl = null;
    }
  }

  function setStatus(value) {
    statusText.textContent = value;
  }

  function showError(error) {
    setStatus("Failed");
    details.textContent = error.message;
    submitButton.disabled = false;
  }

  function formatTime(value) {
    if (!value) {
      return "unknown";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString();
  }

  function formatBytes(value) {
    const bytes = Number(value);
    if (!Number.isFinite(bytes) || bytes <= 0) {
      return "unknown";
    }
    const units = ["B", "KB", "MB", "GB"];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex += 1;
    }
    return (unitIndex === 0 ? size : size.toFixed(1)) + " " + units[unitIndex];
  }

  function shortHash(value) {
    return value ? String(value).slice(0, 12) : "Not available";
  }

  function summarizeMetadata(value) {
    if (!value || typeof value !== "object") {
      return "No metadata";
    }
    const entries = Object.entries(value).filter(([_, item]) => item !== null && item !== undefined && item !== "");
    if (!entries.length) {
      return "No metadata";
    }
    return entries.slice(0, 4).map(([key, item]) => key + ": " + String(item)).join(" | ");
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    }[character]));
  }
})();
