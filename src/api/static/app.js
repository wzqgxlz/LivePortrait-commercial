(function () {
  const form = document.getElementById("job-form");
  const apiKeyInput = document.getElementById("api-key");
  const submitButton = document.getElementById("submit");
  const statusText = document.getElementById("status");
  const details = document.getElementById("details");
  const preview = document.getElementById("preview");
  const downloadLink = document.getElementById("download");
  const health = document.getElementById("health");
  let currentResultUrl = null;

  apiKeyInput.value = localStorage.getItem("liveportrait_api_key") || "";
  apiKeyInput.addEventListener("change", () => {
    localStorage.setItem("liveportrait_api_key", apiKeyInput.value.trim());
  });

  checkHealth();
  form.addEventListener("submit", createJob);

  async function createJob(event) {
    event.preventDefault();
    resetResult();
    submitButton.disabled = true;
    setStatus("Uploading");

    try {
      const body = new FormData(form);
      body.delete("api-key");
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: authHeaders(),
        body,
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "Upload failed");
      }
      details.textContent = "Job " + payload.job_id;
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
    details.textContent = "Job " + payload.job_id + " updated at " + payload.updated_at;

    if (payload.status === "succeeded") {
      await loadResult(jobId);
      submitButton.disabled = false;
      return;
    }

    if (payload.status === "failed") {
      details.textContent = payload.error_message || "Generation failed";
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
    downloadLink.hidden = false;
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

  async function checkHealth() {
    try {
      const response = await fetch("/api/health");
      health.textContent = response.ok ? "Online" : "Offline";
      health.dataset.state = response.ok ? "ok" : "bad";
    } catch (error) {
      health.textContent = "Offline";
      health.dataset.state = "bad";
    }
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
    downloadLink.hidden = true;
    downloadLink.removeAttribute("href");
  }

  function setStatus(value) {
    statusText.textContent = value;
  }

  function showError(error) {
    setStatus("Failed");
    details.textContent = error.message;
    submitButton.disabled = false;
  }
})();
