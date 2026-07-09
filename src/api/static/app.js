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
  const refreshJobsButton = document.getElementById("refresh-jobs");
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
  let maxUploadBytes = null;

  apiKeyInput.value = localStorage.getItem("liveportrait_api_key") || "";
  updateAuthHint();
  apiKeyInput.addEventListener("change", () => {
    localStorage.setItem("liveportrait_api_key", apiKeyInput.value.trim());
    updateAuthHint();
    loadJobs();
  });

  renderEmptyState();
  checkHealth();
  loadJobs();
  form.addEventListener("submit", createJob);
  sourceInput.addEventListener("change", () => {
    renderFileSummary(sourceInput, sourceSummary);
    clearFormErrors();
  });
  drivingInput.addEventListener("change", () => {
    renderFileSummary(drivingInput, drivingSummary);
    clearFormErrors();
  });
  consentInput.addEventListener("change", clearFormErrors);
  jobStatusFilter.addEventListener("change", loadJobs);
  refreshJobsButton.addEventListener("click", loadJobs);
  clearResultButton.addEventListener("click", clearCurrentJob);

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
      const body = new FormData(form);
      body.delete("api-key");
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: authHeaders(),
        body,
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(friendlyError(response.status, payload.detail || "Upload failed"));
      }
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
      const status = jobStatusFilter.value;
      const url = "/api/jobs?limit=10" + (status ? "&status=" + encodeURIComponent(status) : "");
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

  function renderJobs(jobs) {
    jobsList.replaceChildren();
    if (!jobs.length) {
      jobsList.textContent = jobStatusFilter.value ? "No jobs match this status." : "No recent jobs.";
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

  function updateAuthHint() {
    if (apiKeyInput.value.trim()) {
      authHint.textContent = "API Key saved in this browser and sent with job requests.";
      authHint.dataset.state = "ready";
      return;
    }
    authHint.textContent = "Local testing may not require a key. Deployed services usually do.";
    authHint.dataset.state = "neutral";
  }

  function renderJobSummary(job) {
    jobSummary.hidden = false;
    jobSummaryContent.replaceChildren(
      summaryRow("Status", job.status || "unknown"),
      summaryRow("Job ID", job.job_id || "unknown"),
      summaryRow("Files", (job.source_filename || "source") + " -> " + (job.driving_filename || "driving")),
      summaryRow("Created", formatTime(job.created_at)),
      summaryRow("Updated", formatTime(job.updated_at)),
      summaryRow("Source SHA", shortHash(job.source_sha256)),
      summaryRow("Driving SHA", shortHash(job.driving_sha256)),
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
