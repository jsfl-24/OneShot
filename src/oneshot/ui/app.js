(() => {
  const $ = (sel) => document.querySelector(sel);

  const state = {
    projects: [],
    selectedProjectId: null,
    screenplays: [],
    selectedScreenplayId: null,
    scenes: [],
  };

  const els = {
    healthChip: $("#health-chip"),
    healthText: $("#health-text"),
    error: $("#error-banner"),
    projectForm: $("#project-form"),
    projectName: $("#project-name"),
    projectDesc: $("#project-desc"),
    projectList: $("#project-list"),
    projectEmpty: $("#project-empty"),
    uploadForm: $("#upload-form"),
    screenplayFile: $("#screenplay-file"),
    screenplayNote: $("#screenplay-note"),
    screenplayList: $("#screenplay-list"),
    screenplayEmpty: $("#screenplay-empty"),
    sceneNote: $("#scene-note"),
    sceneList: $("#scene-list"),
    sceneEmpty: $("#scene-empty"),
    uploadBtn: document.querySelector("#upload-form button"),
  };

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
        <span class="entry-meta">.${escapeHtml(sp.format)} — ${formatDate(sp.created_at)}</span>`;
      item.addEventListener("click", () => selectScreenplay(sp.id));
      item.setAttribute("role", "button");
      item.tabIndex = 0;

      const actions = document.createElement("div");
      actions.className = "entry-actions";
      const detectBtn = document.createElement("button");
      detectBtn.type = "button";
      detectBtn.className = "ghost";
      detectBtn.textContent = "LLM Detection";
      detectBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        runDetection(sp);
      });
      const pipeBtn = document.createElement("button");
      pipeBtn.type = "button";
      pipeBtn.className = "primary";
      pipeBtn.textContent = "Full Pipeline →";
      pipeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        runFullPipeline(sp);
      });
      actions.appendChild(detectBtn);
      actions.appendChild(pipeBtn);

      li.appendChild(item);
      li.appendChild(actions);
      els.screenplayList.appendChild(li);
    }

    highlightSelected(els.screenplayList, state.selectedScreenplayId);
  }

  async function runDetection(sp) {
    await runLlmAction(sp.id, `/screenplays/${sp.id}/detect-scenes`, "Detection complete.");
  }

  async function runFullPipeline(sp) {
    await runLlmAction(sp.id, `/screenplays/${sp.id}/full-pipeline`, "Analysis complete.");
  }

  async function runLlmAction(screenplayId, path, doneText) {
    clearError();
    try {
      const data = await api(path, { method: "POST" });
      if (String(state.selectedScreenplayId) === String(screenplayId)) {
        state.scenes = data.scenes ?? [];
        els.sceneEmpty.textContent = "No scenes detected in this screenplay.";
        renderScenes();
      }
      alert(doneText);
    } catch (err) {
      showError(err.message);
    }
  }

  function renderScenes() {
    els.sceneList.textContent = "";
    els.sceneEmpty.hidden = state.scenes.length > 0;

    for (const scene of state.scenes) {
      const details = document.createElement("details");
      details.className = "scene";
      const summary = document.createElement("summary");
      summary.innerHTML =
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
        analyzeBtn.className = "ghost";
        analyzeBtn.textContent = "Analyze";
        analyzeBtn.addEventListener("click", () => analyzeScene(scene));
        details.appendChild(analyzeBtn);
      }

      els.sceneList.appendChild(details);
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
    els.sceneNote.textContent = "Select a screenplay to see its detected scenes.";
    els.screenplayEmpty.hidden = false;
    els.screenplayEmpty.textContent = "Loading screenplays…";

    try {
      const data = await api(`/screenplays/projects/${id}`);
      state.screenplays = data;
      els.screenplayEmpty.textContent = "No screenplays in this project yet. Upload one above.";
      renderScreenplays();
    } catch (err) {
      state.screenplays = [];
      els.screenplayEmpty.textContent = "Could not load screenplays.";
      showError(err.message);
      renderScreenplays();
    }
  }

  async function selectScreenplay(id) {
    state.selectedScreenplayId = id;
    renderScreenplays();

    const sp = state.screenplays.find((s) => String(s.id) === String(id));
    els.sceneNote.textContent = sp ? `Scenes detected in “${sp.filename}”.` : "";
    els.sceneList.textContent = "";
    state.scenes = [];
    els.sceneEmpty.hidden = false;
    els.sceneEmpty.textContent = "Reading scenes…";

    try {
      const data = await api(`/screenplays/${id}/scenes`);
      state.scenes = data.scenes ?? [];
      els.sceneEmpty.textContent = "No scenes detected in this screenplay.";
      renderScenes();
    } catch (err) {
      state.scenes = [];
      els.sceneEmpty.textContent = "Could not load scenes.";
      showError(err.message);
      renderScenes();
    }
  }

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
      const data = await api(`/screenplays/projects/${state.selectedProjectId}/upload`, {
        method: "POST",
        body: formData,
      });
      els.screenplayFile.value = "";
      state.screenplays.push(data);
      await selectScreenplay(data.id);
      renderScreenplays();
    } catch (err) {
      showError(err.message);
    } finally {
      els.uploadBtn.disabled = false;
    }
  }

  async function loadHealth() {
    try {
      const data = await api("/health");
      const llm = data.llm ?? {};
      const emb = data.embeddings ?? {};
      els.healthText.textContent = `${llm.provider} — ${llm.model}`;
      if (emb.provider && emb.provider !== "ollama") {
        els.healthText.textContent += ` · embeddings: ${emb.provider}`;
      }
      els.healthChip.classList.add("is-ok");
    } catch (err) {
      els.healthText.textContent = "health check failed";
    }
  }

  els.projectForm.addEventListener("submit", onProjectCreate);
  els.uploadForm.addEventListener("submit", onUpload);

  loadProjects();
  loadHealth();
})();