(() => {
  const $ = (sel) => document.querySelector(sel);

  const state = {
    currentStep: 1,
    projects: [],
    selectedProjectId: null,
    screenplays: [],
    selectedScreenplayId: null,
    scenes: [],
    health: null,
  };

  const els = {
    progressContainer: $("#progress-container"),
    progressBar: $("#progress-bar"),
    progressLabel: $("#progress-label"),
    healthChip: $("#health-chip"),
    healthText: $("#health-text"),
    settingsToggle: $("#settings-toggle"),
    settingsPanel: $("#settings-panel"),
    llmProvider: $("#llm-provider"),
    embedProvider: $("#embedding-provider"),
    pingBtn: $("#ping-btn"),
    error: $("#error-banner"),
    projectForm: $("#project-form"),
    projectName: $("#project-name"),
    projectDesc: $("#project-desc"),
    projectList: $("#project-list"),
    projectEmpty: $("#project-empty"),
    uploadForm: $("#upload-form"),
    uploadBtn: $("#upload-btn"),
    screenplayFile: $("#screenplay-file"),
    filePicker: document.querySelector(".file-picker"),
    screenplayNote: $("#screenplay-note"),
    pipelineNote: $("#pipeline-note"),
    screenplayList: $("#screenplay-list"),
    screenplayEmpty: $("#screenplay-empty"),
    sceneNote: $("#scene-note"),
    sceneList: $("#scene-list"),
    sceneEmpty: $("#scene-empty"),
    screenplayMeta: $("#screenplay-meta"),
    screenplayMetaEmpty: $("#screenplay-meta-empty"),
    btnDetect: $("#btn-detect"),
    btnFullPipeline: $("#btn-full-pipeline"),
    step1Next: $("#step1-next"),
    step2Next: $("#step2-next"),
    step3Next: $("#step3-next"),
  };

  function showProgress(label) {
    els.progressContainer.hidden = false;
    els.progressBar.style.width = "0%";
    els.progressLabel.textContent = label;
  }

  function updateProgress(percent, label) {
    els.progressContainer.hidden = false;
    els.progressBar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
    if (label) els.progressLabel.textContent = label;
  }

  function hideProgress() {
    els.progressContainer.hidden = true;
  }

  function showError(message) {
    if (!message) return;
    els.error.textContent = message;
    els.error.hidden = false;
  }

  function clearError() {
    els.error.hidden = true;
    els.error.textContent = "";
  }

  async function api(path, options = {}) {
    clearError();
    const response = await fetch(path, options);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const detail =
        data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `Request failed with ${response.status}`;
      throw new Error(detail);
    }
    return data;
  }

  /* ---------- Step navigation ---------- */

  function goToStep(step) {
    state.currentStep = step;
    document.querySelectorAll(".step-panel").forEach((panel) => {
      panel.classList.toggle("is-active", Number(panel.dataset.panel) === step);
    });
    document.querySelectorAll(".steps-nav .step").forEach((elt) => {
      const n = Number(elt.dataset.step);
      elt.classList.toggle("is-active", n === step);
      elt.classList.toggle("is-done", n < step);
    });
    refreshStepButtons();
  }

  function refreshStepButtons() {
    const hasProject = state.selectedProjectId != null;
    const hasScreenplay = state.selectedScreenplayId != null;
    const hasScenes = state.scenes.length > 0;
    els.step1Next.disabled = !hasProject;
    els.step2Next.disabled = !hasScreenplay;
    els.step3Next.disabled = !hasScenes;
    els.uploadForm.hidden = !hasProject;
    els.pipelineNote.textContent = hasScreenplay
      ? "Detect scenes, analyze the screenplay, and extract film metadata."
      : "Select a screenplay in the previous step first.";
    els.btnDetect.disabled = !hasScreenplay;
    els.btnFullPipeline.disabled = !hasScreenplay;
    if (!hasScreenplay) {
      els.screenplayMeta.textContent = "";
      els.screenplayMetaEmpty.hidden = false;
      els.screenplayMetaEmpty.textContent = "Upload a screenplay to see its film metadata.";
      els.sceneList.textContent = "";
      els.sceneEmpty.hidden = false;
      els.sceneEmpty.textContent = "Upload a screenplay to see its detected scenes.";
    }
  }

  document.querySelectorAll("[data-goto]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = Number(btn.dataset.goto);
      if (target === 3 && !state.selectedScreenplayId) {
        showError("Select a screenplay before continuing.");
        return;
      }
      if (target === 4 && state.scenes.length === 0) {
        showError("Run detection or the full pipeline before reviewing scenes.");
        return;
      }
      goToStep(target);
    });
  });

  /* ---------- Rendering ---------- */

  function renderProjects() {
    els.projectList.textContent = "";
    els.projectEmpty.hidden = state.projects.length > 0;

    for (const project of state.projects) {
      const li = document.createElement("li");
      const item = document.createElement("div");
      item.className = "entry-item";
      item.dataset.entryId = project.id;
      item.innerHTML = `<span class="entry-from">${escapeHtml(project.name)}</span>`;
      if (project.description) {
        item.innerHTML += `<span class="entry-meta">${escapeHtml(project.description)}</span>`;
      }
      item.addEventListener("click", () => selectProject(project.id));
      item.setAttribute("role", "button");
      item.tabIndex = 0;
      li.appendChild(item);
      els.projectList.appendChild(li);
    }

    highlightSelected(els.projectList, state.selectedProjectId);
  }

  function renderScreenplays() {
    els.screenplayList.textContent = "";
    els.screenplayEmpty.hidden = state.screenplays.length > 0;

    for (const sp of state.screenplays) {
      const li = document.createElement("li");
      const item = document.createElement("div");
      item.className = "entry-item";
      item.dataset.entryId = sp.id;
      item.innerHTML = `<span class="entry-from">${escapeHtml(sp.filename)}</span>
        <span class="entry-meta">.${escapeHtml(sp.format)} — ${formatDate(sp.created_at)}${sp.analyzed ? " — metadata ready" : ""}</span>`;
      item.addEventListener("click", () => selectScreenplay(sp.id));
      item.setAttribute("role", "button");
      item.tabIndex = 0;
      li.appendChild(item);
      els.screenplayList.appendChild(li);
    }

    highlightSelected(els.screenplayList, state.selectedScreenplayId);
  }

  function renderScreenplayMeta() {
    els.screenplayMeta.textContent = "";
    const sp = state.screenplays.find((s) => String(s.id) === String(state.selectedScreenplayId));
    els.screenplayMetaEmpty.hidden = !!(sp && (sp.one_liner || sp.genre || sp.story_abstract));

    if (!sp) return;

    const meta = document.createElement("div");
    meta.className = "meta-block";
    meta.innerHTML =
      `<div><strong>One-liner:</strong> ${escapeHtml(sp.one_liner ?? "—")}</div>` +
      `<div><strong>Genre:</strong> ${escapeHtml(sp.genre ?? "—")}</div>` +
      `<div><strong>Story abstract:</strong> ${escapeHtml(sp.story_abstract ?? "—")}</div>` +
      `<div><strong>Characters:</strong> ${escapeHtml((sp.characters ?? []).join(", ") || "—")}</div>`;
    els.screenplayMeta.appendChild(meta);

    if (!sp.analyzed) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn ghost";
      btn.textContent = "Analyze Screenplay";
      btn.addEventListener("click", () => analyzeScreenplay(sp));
      els.screenplayMeta.appendChild(btn);
    } else {
      const tag = document.createElement("span");
      tag.className = "analyzed-tag";
      tag.textContent = "analyzed";
      els.screenplayMeta.appendChild(tag);
    }
  }

  function renderScenes() {
    els.sceneList.textContent = "";
    els.sceneEmpty.hidden = state.scenes.length > 0;

    for (const [index, scene] of state.scenes.entries()) {
      const details = document.createElement("details");
      details.className = "scene";
      const summary = document.createElement("summary");
      summary.innerHTML =
        `<span class="scene-number">${index + 1}</span>` +
        `<span class="scene-heading">${escapeHtml(scene.heading)}</span>` +
        `<span class="scene-slug">${escapeHtml(scene.location ?? "")}${scene.time_of_day ? " — " + escapeHtml(scene.time_of_day) : ""}</span>`;
      const pre = document.createElement("pre");
      pre.textContent = scene.raw_text ?? "";
      details.appendChild(summary);
      details.appendChild(pre);

      const meta = document.createElement("div");
      meta.className = "scene-meta";
      if (scene.analyzed) {
        meta.innerHTML =
          `<div class="meta-block"><strong>Characters:</strong> ${escapeHtml((scene.characters ?? []).join(", "))}</div>` +
          `<div class="meta-block"><strong>Actions:</strong> ${escapeHtml((scene.actions ?? []).join(" | "))}</div>` +
          `<div class="meta-block"><strong>Dialogue:</strong> ${escapeHtml((scene.dialogue ?? []).join(" | "))}</div>` +
          (scene.narrative_context
            ? `<div class="meta-block"><strong>Context:</strong> ${escapeHtml(scene.narrative_context)}</div>`
            : "");
        meta.innerHTML += `<span class="analyzed-tag">analyzed</span>`;
      }
      details.appendChild(meta);

      if (!scene.analyzed) {
        const analyzeBtn = document.createElement("button");
        analyzeBtn.type = "button";
        analyzeBtn.className = "btn ghost";
        analyzeBtn.textContent = "Analyze";
        analyzeBtn.addEventListener("click", () => analyzeScene(scene));
        details.appendChild(analyzeBtn);
      }

      els.sceneList.appendChild(details);
    }
  }

  function highlightSelected(listEl, selectedId) {
    for (const item of listEl.querySelectorAll(".entry-item")) {
      const id = item.dataset.entryId;
      item.classList.toggle("is-selected", String(selectedId) === id);
    }
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[c]);
  }

  function formatDate(value) {
    if (!value) return "";
    return new Date(value).toLocaleDateString();
  }

  /* ---------- Actions ---------- */

  async function runDetection(sp) {
    await runLlmAction(sp, `/screenplays/${sp.id}/detect-scenes`, "Detection complete.");
  }

  async function runFullPipeline(sp) {
    clearError();
    showProgress(`Running full pipeline for "${sp.filename}"...`);
    try {
      const response = await fetch(`/screenplays/${sp.id}/full-pipeline-stream`, { method: "POST" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const raw of events) {
          const lines = raw.split("\n");
          const eventType = lines.find((l) => l.startsWith("event:"))?.slice(6).trim() ?? "message";
          const dataLine = lines.find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          const data = JSON.parse(dataLine.slice(5).trim());

          if (eventType === "progress") {
            updateProgress(data.percent ?? 0, data.detail || data.step || "");
          } else if (eventType === "complete") {
            updateProgress(100, "Complete.");
            if (String(state.selectedScreenplayId) === String(sp.id)) {
              state.scenes = data.scenes ?? [];
              els.sceneNote.textContent = `${data.total_scenes ?? state.scenes.length} scenes detected in "${sp.filename}".`;
              const idx = state.screenplays.findIndex((s) => String(s.id) === String(sp.id));
              if (idx !== -1 && data.screenplay) state.screenplays[idx] = data.screenplay;
              renderScenes();
              renderScreenplayMeta();
              refreshStepButtons();
            }
          } else if (eventType === "error") {
            throw new Error(data.message || "Pipeline failed.");
          }
        }
      }
    } catch (err) {
      showError(err.message);
    } finally {
      hideProgress();
    }
  }

  async function runLlmAction(sp, path, doneText) {
    clearError();
    showProgress(`Running ${doneText}`.replace(" complete.", "…"));
    try {
      const data = await api(path, { method: "POST" });
      if (String(state.selectedScreenplayId) === String(sp.id)) {
        state.scenes = data.scenes ?? [];
        els.sceneEmpty.textContent = "No scenes detected in this screenplay.";
        renderScenes();
        const spIdx = state.screenplays.findIndex((s) => String(s.id) === String(sp.id));
        if (spIdx !== -1) {
          state.screenplays[spIdx] = await api(`/screenplays/${sp.id}`);
          renderScreenplayMeta();
        }
        refreshStepButtons();
      }
      updateProgress(100, doneText);
    } catch (err) {
      showError(err.message);
    } finally {
      setTimeout(hideProgress, 800);
    }
  }

  async function analyzeScreenplay(sp) {
    clearError();
    try {
      const data = await api(`/screenplays/${sp.id}/analyze`, { method: "POST" });
      const idx = state.screenplays.findIndex((s) => String(s.id) === String(data.id));
      if (idx !== -1) state.screenplays[idx] = data;
      renderScreenplayMeta();
    } catch (err) {
      showError(err.message);
    }
  }

  async function analyzeScene(scene) {
    clearError();
    try {
      const data = await api(`/scenes/${scene.id}/analyze`, { method: "POST" });
      const idx = state.scenes.findIndex((s) => String(s.id) === String(data.id));
      if (idx !== -1) state.scenes[idx] = data;
      renderScenes();
    } catch (err) {
      showError(err.message);
    }
  }

  /* ---------- Selection ---------- */

  async function selectProject(id) {
    state.selectedProjectId = id;
    renderProjects();

    const project = state.projects.find((p) => String(p.id) === String(id));
    els.screenplayNote.textContent = project ? `Screenplays in “${project.name}”.` : "";
    els.screenplayList.textContent = "";
    state.selectedScreenplayId = null;
    state.screenplays = [];
    state.scenes = [];
    els.sceneList.textContent = "";
    els.screenplayMeta.textContent = "";
    els.screenplayMetaEmpty.hidden = false;
    els.sceneNote.textContent = "Select a screenplay to see its detected scenes.";
    els.sceneEmpty.textContent = "Select a screenplay to see its detected scenes.";
    els.screenplayEmpty.hidden = false;
    els.screenplayEmpty.textContent = "Loading screenplays…";

    try {
      const data = await api(`/screenplays/projects/${id}`);
      state.screenplays = data;
      els.screenplayEmpty.textContent = "No screenplays in this project yet. Upload one below.";
      renderScreenplays();
    } catch (err) {
      state.screenplays = [];
      els.screenplayEmpty.textContent = "Could not load screenplays.";
      showError(err.message);
      renderScreenplays();
    } finally {
      refreshStepButtons();
    }
  }

  async function selectScreenplay(id) {
    state.selectedScreenplayId = id;
    renderScreenplays();

    const sp = state.screenplays.find((s) => String(s.id) === String(id));
    els.sceneNote.textContent = sp ? `Scenes detected in “${sp.filename}”.` : "";
    els.sceneList.textContent = "";
    els.screenplayMeta.textContent = "";
    els.screenplayMetaEmpty.hidden = false;
    state.scenes = [];
    els.sceneEmpty.hidden = false;
    els.sceneEmpty.textContent = "Reading scenes…";

    renderScreenplayMeta();

    try {
      const data = await api(`/screenplays/${id}/scenes`);
      state.scenes = data.scenes ?? [];
      els.sceneEmpty.textContent = "No scenes detected in this screenplay.";
      els.sceneNote.textContent = sp ? `${data.total_scenes} scenes detected in “${sp.filename}”.` : "";
      renderScenes();
    } catch (err) {
      state.scenes = [];
      els.sceneEmpty.textContent = "Could not load scenes.";
      showError(err.message);
      renderScenes();
    } finally {
      refreshStepButtons();
    }
  }

  /* ---------- Load & onboarding ---------- */

  async function loadProjects() {
    try {
      state.projects = await api("/projects");
      els.projectEmpty.textContent = "No projects yet. Create one to begin.";
      renderProjects();
      if (state.projects.length === 1) {
        await selectProject(state.projects[0].id);
      }
    } catch (err) {
      els.projectEmpty.textContent = "Could not load projects.";
      showError(err.message);
    } finally {
      refreshStepButtons();
    }
  }

  async function onProjectCreate(event) {
    event.preventDefault();
    const name = els.projectName.value.trim();
    const description = els.projectDesc.value.trim() || null;
    if (!name) return;

    const button = els.projectForm.querySelector("button");
    button.disabled = true;
    try {
      await api("/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description }),
      });
      els.projectName.value = "";
      els.projectDesc.value = "";
      await loadProjects();
      const created = state.projects.find((p) => p.name === name);
      if (created) {
        await selectProject(created.id);
        goToStep(2);
      }
    } catch (err) {
      showError(err.message);
    } finally {
      button.disabled = false;
    }
  }

  async function onUpload(event) {
    event.preventDefault();
    const file = els.screenplayFile.files[0];
    if (!state.selectedProjectId || !file) return;

    const formData = new FormData();
    formData.append("file", file);

    els.uploadBtn.disabled = true;
    try {
      showProgress(`Uploading “${file.name}”…`);
      updateProgress(15, "Uploading…");
      const data = await api(`/screenplays/projects/${state.selectedProjectId}/upload`, {
        method: "POST",
        body: formData,
      });
      updateProgress(100, "Upload complete.");
      els.screenplayFile.value = "";
      state.screenplays.push(data);
      await selectScreenplay(data.id);
      renderScreenplays();
      renderScreenplayMeta();
      goToStep(2);
      refreshStepButtons();
    } catch (err) {
      showError(err.message);
    } finally {
      hideProgress();
      els.uploadBtn.disabled = false;
    }
  }

  /* ---------- Providers & health ---------- */

  function renderHealth(data) {
    const llm = data.llm ?? {};
    const emb = data.embeddings ?? {};
    els.healthText.textContent = `${llm.provider} — ${llm.model}`;
    if (emb.provider && emb.provider !== "ollama") {
      els.healthText.textContent += ` · embeddings: ${emb.provider}`;
    }
    if (llm.provider) els.llmProvider.value = llm.provider;
    if (emb.provider) els.embedProvider.value = emb.provider;
    els.healthChip.classList.add("is-ok");
    state.health = data;
  }

  async function loadHealth() {
    try {
      renderHealth(await api("/health"));
    } catch (err) {
      els.healthText.textContent = "health check failed";
    }
  }

  async function switchProvider(which, value) {
    clearError();
    const body =
      which === "llm" ? { llm_provider: value } : { embedding_provider: value };
    try {
      const status = await api("/providers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      renderHealth(status);
    } catch (err) {
      showError(err.message);
    }
  }

  async function pingProviders() {
    const btn = els.pingBtn;
    btn.disabled = true;
    btn.textContent = "Pinging…";
    clearError();
    try {
      const data = await api("/providers/ping", { method: "POST" });
      const errs = [];
      const lat = [];
      if (data.llm.latency_ms != null) lat.push(`LLM ${data.llm.latency_ms}ms`);
      else errs.push(`LLM: ${data.llm.error}`);
      if (data.embeddings.latency_ms != null) lat.push(`emb ${data.embeddings.latency_ms}ms`);
      else errs.push(`embeddings: ${data.embeddings.error}`);
      if (state.health) renderHealth(state.health);
      els.healthText.textContent += lat.length ? ` · ping ${lat.join(" · ")}` : "";
      els.healthChip.classList.toggle("is-ok", !errs.length);
      if (errs.length) {
        showError(`Ping failed — ${errs.join(" · ")}`);
      }
    } catch (err) {
      showError(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Ping";
    }
  }

  /* ---------- Wiring ---------- */

  els.projectForm.addEventListener("submit", onProjectCreate);
  els.uploadForm.addEventListener("submit", onUpload);
  els.llmProvider.addEventListener("change", (e) => switchProvider("llm", e.target.value));
  els.embedProvider.addEventListener("change", (e) => switchProvider("embeddings", e.target.value));
  els.pingBtn.addEventListener("click", pingProviders);
  els.screenplayFile.addEventListener("change", () => {
    const file = els.screenplayFile.files[0];
    if (els.filePicker) els.filePicker.textContent = file ? file.name : "Choose file…";
  });

  els.settingsToggle.addEventListener("click", () => {
    const open = els.settingsPanel.hidden;
    els.settingsPanel.hidden = !open;
    els.settingsToggle.setAttribute("aria-expanded", String(open));
  });

  document.querySelectorAll(".steps-nav .step").forEach((step) => {
    step.addEventListener("click", () => {
      const target = Number(step.dataset.step);
      if (target === 3 && !state.selectedScreenplayId) {
        showError("Select a screenplay before continuing.");
        return;
      }
      if (target === 4 && state.scenes.length === 0) {
        showError("Run detection or the full pipeline before reviewing scenes.");
        return;
      }
      goToStep(target);
    });
  });

  els.btnDetect.addEventListener("click", () => {
    const sp = state.screenplays.find((s) => String(s.id) === String(state.selectedScreenplayId));
    if (sp) runDetection(sp);
  });
  els.btnFullPipeline.addEventListener("click", () => {
    const sp = state.screenplays.find((s) => String(s.id) === String(state.selectedScreenplayId));
    if (sp) runFullPipeline(sp);
  });

  loadProjects();
  loadHealth();
})();