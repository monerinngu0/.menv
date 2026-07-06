const jobs = new Map();
let selectedLibraryFiles = [];

const $ = (id) => document.getElementById(id);

function setStatus(message, isError = false) {
    const status = $("status");
    status.textContent = message;
    status.className = isError ? "error" : "";
}

async function fetchJson(url, options) {
    const res = await fetch(url, options);
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
    }
    return data;
}

async function createJob(payload) {
    setStatus("Creating job...");
    const job = await fetchJson("/api/jobs", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    jobs.set(job.id, job);
    renderJobs();
    watchJob(job.id);
    setStatus(`Job created: ${job.id}`);
}

async function watchJob(jobId) {
    const job = await fetchJson(`/api/jobs/${jobId}`);
    jobs.set(jobId, job);
    renderJobs();

    if (job.status === "queued" || job.status === "running") {
        setTimeout(() => watchJob(jobId), 1000);
    }
}

function renderJobs() {
    const root = $("jobs");
    const values = [...jobs.values()].sort((a, b) => String(b.created || "").localeCompare(String(a.created || "")));

    if (values.length === 0) {
    root.innerHTML = '<div class="meta">No jobs yet.</div>';
    return;
  }

  root.innerHTML = values.map((job) => {
    const outputs = (job.outputs || []).map((out) => (
      `<a href="${out.url}" download>${out.name}</a>`
    )).join(" ");
    const error = job.error ? `<div class="meta error">${escapeHtml(job.error)}</div>` : "";
    return `
      <div class="job">
        <div class="job-title">${escapeHtml(job.type)} / ${escapeHtml(job.status)}</div>
        <div class="meta">${escapeHtml(job.id)}</div>
        ${error}
        <div class="meta">${outputs}</div>
      </div>
    `;
  }).join("");
}

async function loadLibrary() {
  const data = await fetchJson("/api/library");
  const root = $("library");
  const categories = data.categories || [];

  if (categories.length === 0) {
    root.innerHTML = '<div class="meta">No categories.</div>';
    return;
  }

  root.innerHTML = categories.map((cat) => `
    <div class="item">
      <div class="item-title">${escapeHtml(cat.category)}</div>
      <div class="meta">${cat.files.length} files</div>
    </div>
  `).join("");
}

async function loadSelectLibrary() {
  const category = $("pack-select-category").value.trim();
  if (!category) {
    throw new Error("category is required");
  }

  const data = await fetchJson(`/api/library?category=${encodeURIComponent(category)}`);
  selectedLibraryFiles = data.files || [];
  renderSelectFiles(selectedLibraryFiles);
  setStatus(`Loaded ${selectedLibraryFiles.length} files`);
}

function renderSelectFiles(files) {
  const root = $("select-files");

  if (files.length === 0) {
    root.innerHTML = '<div class="meta">No files.</div>';
    return;
  }

  root.innerHTML = files.map((file, index) => `
    <label class="file-check">
      <input type="checkbox" class="select-file-check" value="${escapeHtml(file)}" data-index="${index}">
      ${escapeHtml(file)}
    </label>
  `).join("");
}

function selectedFiles() {
  return [...document.querySelectorAll(".select-file-check")]
    .filter((input) => input.checked)
    .map((input) => input.value);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function bindActions() {
  $("add-button").addEventListener("click", async () => {
    try {
      await createJob({
        type: "song_add",
        url: $("add-url").value.trim(),
        category: $("add-category").value.trim(),
        playlist: $("add-playlist").checked,
      });
    } catch (e) {
      setStatus(e.message, true);
    }
  });

  $("pack-all-button").addEventListener("click", async () => {
    try {
      await createJob({
        type: "song_pack_all",
        category: $("pack-all-category").value.trim(),
      });
    } catch (e) {
      setStatus(e.message, true);
    }
  });

  $("pack-diff-button").addEventListener("click", async () => {
    try {
      await createJob({
        type: "song_pack_diff",
        category: $("pack-diff-category").value.trim(),
        client_files: JSON.parse($("client-files").value || "[]"),
      });
    } catch (e) {
      setStatus(e.message, true);
    }
  });

  $("load-select-library").addEventListener("click", async () => {
    try {
      await loadSelectLibrary();
    } catch (e) {
      setStatus(e.message, true);
    }
  });

  $("select-all-button").addEventListener("click", () => {
    document.querySelectorAll(".select-file-check").forEach((input) => {
      input.checked = true;
    });
  });

  $("clear-select-button").addEventListener("click", () => {
    document.querySelectorAll(".select-file-check").forEach((input) => {
      input.checked = false;
    });
  });

  $("pack-selected-button").addEventListener("click", async () => {
    try {
      const files = selectedFiles();
      if (files.length === 0) {
        throw new Error("no files selected");
      }
      await createJob({
        type: "song_pack_select",
        category: $("pack-select-category").value.trim(),
        files,
      });
    } catch (e) {
      setStatus(e.message, true);
    }
  });

  $("refresh-library").addEventListener("click", async () => {
    try {
      await loadLibrary();
      setStatus("Library refreshed");
    } catch (e) {
      setStatus(e.message, true);
    }
  });
}

bindActions();
renderJobs();
loadLibrary().catch((e) => setStatus(e.message, true));
