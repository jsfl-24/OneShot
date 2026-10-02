(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const ACTIVITY_KEY = "oneshot.activity";
  const ACTION_TIP_ATTRIBUTE = "data-tip";

  const state = {
    activeTab: "pipeline",
    projects: [],
    selectedProjectId: null,
    screenplays: [],
    selectedScreenplayId: null,
    scenes: [],
    health: null,
    shotsByScene: {},
    shotWarningsByScene: {},
    projectConstraints: null,
    projectConstraintsLoaded: false,
    sceneConstraintsLoaded: {},
    sceneEffectiveConstraints: {},
    screenplaysLoadedFor: null,
    screenplaysLoadingFor: null,
    scenesLoadedFor: null,
    shotsLoadedFor: null,
    scenesLoading: false,
    shotsLoading: false,
    pipelineInProgress: false,
    shotGenerationInProgress: false,
    activeShotSceneId: null,
    projectConstraintsLoading: false,
    projectConstraintSaveInProgress: false,
    projectConstraintResetInProgress: false,
    sceneConstraintSaveInProgress: null,
    activityEntries: [],
    lastErrorMessage: null,
  };

  const els = {
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
    projectCount: $("#project-count"),
    uploadForm: $("#upload-form"),
    uploadBtn: $("#upload-btn"),
    screenplayFile: $("#screenplay-file"),
    filePicker: $(".file-picker"),
    screenplayNote: $("#screenplay-note"),
    screenplayList: $("#screenplay-list"),
    screenplayEmpty: $("#screenplay-empty"),
    screenplayCount: $("#screenplay-count"),
    pipelineNote: $("#pipeline-note"),
    screenplayMeta: $("#screenplay-meta"),
    screenplayMetaEmpty: $("#screenplay-meta-empty"),
    btnDetect: $("#btn-detect"),
    btnFullPipeline: $("#btn-full-pipeline"),
    pipelineGenerateShots: $("#pipeline-generate-shots"),
    sceneNote: $("#scene-note"),
    sceneList: $("#scene-list"),
    sceneEmpty: $("#scene-empty"),
    btnGenerateAll: $("#btn-generate-all"),
    batchReplace: $("#batch-replace"),
    shotWarnings: $("#shot-warnings"),
    shotSceneList: $("#shot-scene-list"),
    shotEmpty: $("#shot-empty"),
    projectConstraints: $("#project-constraints"),
    projectConstraintsForm: $("#project-constraints-form"),
    saveProjectConstraints: $("#save-project-constraints"),
    resetProjectConstraints: $("#reset-project-constraints"),
    sceneConstraintsList: $("#scene-constraints-list"),
    sceneConstraintsEmpty: $("#scene-constraints-empty"),
    activityConsole: $("#activity-console"),
    activityLog: $("#activity-log"),
    activityEmpty: $("#activity-empty"),
    taskCard: $("#task-card"),
    taskLabel: $("#task-label"),
    taskBar: $("#task-bar"),
    taskPercent: $("#task-percent"),
    taskDetail: $("#task-detail"),
    taskElapsed: $("#task-elapsed"),
  };

  const taskRuntime = {
    nextId: 0,
    active: new Map(),
    displayedId: null,
  };

  const CONSTRAINT_FIELDS = [
    "location_constraints",
    "camera_movement_allowed",
    "high_angle_possible",
    "low_angle_possible",
    "available_lenses",
    "equipment_constraints",
    "director_preferences",
    "additional_notes",
  ];
  const CAMERA_MOVEMENTS = ["Static", "Pan", "Tilt", "Dolly", "Track", "Crane", "Handheld"];
  const BOOLEAN_CONSTRAINT_FIELDS = new Set(["high_angle_possible", "low_angle_possible"]);

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function sameId(left, right) {
    return left != null && right != null && String(left) === String(right);
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);
  }

  function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
  }

  function jsonRequest(method, body) {
    return {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    };
  }

  async function api(path, options = {}) {
    clearError();
    const response = await fetch(path, options);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const detail =
        data && data.detail
          ? typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail)
          : `Request failed with ${response.status}`;
      throw new Error(detail);
    }
    return data;
  }

  function clearError() {
    if (!els.error) return;
    els.error.hidden = true;
    els.error.textContent = "";
  }

  function logEvent(kind, message, options = {}) {
    const normalizedKind = ["ok", "error", "info"].includes(kind) ? kind : "info";
    const text = String(message ?? "").trim();
    if (!text) return;
    const dedupeKey = options.dedupeKey || text;
    if (normalizedKind === "error" && state.lastErrorMessage === dedupeKey) return;
    if (normalizedKind === "error") {
      state.lastErrorMessage = dedupeKey;
    } else {
      state.lastErrorMessage = null;
    }
    const entry = {
      kind: normalizedKind,
      message: text,
      timestamp: new Date().toISOString(),
    };
    state.activityEntries.unshift(entry);
    state.activityEntries = state.activityEntries.slice(0, 100);
    try {
      sessionStorage.setItem(ACTIVITY_KEY, JSON.stringify(state.activityEntries));
    } catch (error) {
      state.lastErrorMessage = null;
    }
    renderActivity();
  }

  function formatTimestamp(value) {
    const date = value ? new Date(value) : new Date();
    return Number.isNaN(date.getTime()) ? "--:--:--" : date.toTimeString().slice(0, 8);
  }

  function renderActivity() {
    if (!els.activityLog) return;
    els.activityLog.textContent = "";
    for (const entry of state.activityEntries) {
      const item = document.createElement("li");
      item.className = `activity-entry is-${entry.kind}`;
      const time = document.createElement("time");
      time.className = "activity-time";
      time.dateTime = entry.timestamp;
      time.textContent = formatTimestamp(entry.timestamp);
      const message = document.createElement("span");
      message.className = "activity-message";
      message.textContent = entry.message;
      item.append(time, message);
      els.activityLog.appendChild(item);
    }
    if (els.activityEmpty) els.activityEmpty.hidden = state.activityEntries.length > 0;
  }

  function hydrateActivity() {
    try {
      const stored = JSON.parse(sessionStorage.getItem(ACTIVITY_KEY) || "[]");
      if (Array.isArray(stored)) {
        state.activityEntries = stored
          .filter((entry) => entry && typeof entry.message === "string")
          .slice(0, 100)
          .map((entry) => ({
            kind: ["ok", "error", "info"].includes(entry.kind) ? entry.kind : "info",
            message: entry.message,
            timestamp: entry.timestamp || new Date().toISOString(),
          }));
      }
    } catch (error) {
      state.activityEntries = [];
    }
    renderActivity();
    logEvent("info", "[session start]");
  }

  function showError(message) {
    const text = String(message ?? "").trim();
    if (!text || !els.error) return;
    els.error.textContent = text;
    els.error.hidden = false;
    logEvent("error", text);
  }

  function formatElapsed(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const minutes = Math.floor(total / 60);
    const remainder = total % 60;
    return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  }

  function formatDuration(seconds) {
    return `${Math.max(0, Number(seconds) || 0).toFixed(1)}s`;
  }

  function paintTask(task) {
    if (!task || !els.taskCard) return;
    els.taskCard.hidden = false;
    els.taskCard.setAttribute("aria-busy", "true");
    els.taskLabel.textContent = task.label;
    els.taskPercent.textContent = task.indeterminate ? "…" : `${Math.round(task.percent)}%`;
    els.taskBar.classList.toggle("is-indeterminate", task.indeterminate);
    els.taskBar.style.width = task.indeterminate ? "34%" : `${task.percent}%`;
    els.taskDetail.textContent = task.detail || "Working…";
    els.taskElapsed.textContent = formatElapsed(task.elapsedSeconds);
  }

  function startTask(label) {
    const id = ++taskRuntime.nextId;
    const task = {
      id,
      label: String(label || "Working"),
      startedAt: Date.now(),
      elapsedSeconds: 0,
      percent: 0,
      detail: "Working…",
      indeterminate: false,
      timer: null,
    };
    taskRuntime.active.set(id, task);
    taskRuntime.displayedId = id;
    paintTask(task);
    task.timer = setInterval(() => {
      task.elapsedSeconds = (Date.now() - task.startedAt) / 1000;
      if (taskRuntime.displayedId === id) {
        els.taskElapsed.textContent = formatElapsed(task.elapsedSeconds);
      }
    }, 1000);
    return id;
  }

  function updateTask(percent, detail, taskId = taskRuntime.displayedId) {
    const task = taskRuntime.active.get(taskId);
    if (!task) return;
    const numeric = Number(percent);
    if (percent == null || !Number.isFinite(numeric)) {
      task.indeterminate = true;
      task.percent = 0;
    } else {
      task.indeterminate = false;
      task.percent = Math.min(100, Math.max(0, numeric));
    }
    if (detail !== undefined && detail !== null) task.detail = String(detail);
    task.elapsedSeconds = (Date.now() - task.startedAt) / 1000;
    if (taskRuntime.displayedId === taskId) paintTask(task);
  }

  function hideTaskCard() {
    if (!els.taskCard) return;
    els.taskCard.hidden = true;
    els.taskCard.setAttribute("aria-busy", "false");
    els.taskBar.classList.remove("is-indeterminate");
  }

  function withDuration(message, seconds) {
    const text = String(message || "Complete").trim();
    if (/\(\d+(?:\.\d+)?s\)$/i.test(text)) return text;
    return `${text} (${formatDuration(seconds)})`;
  }

  function endTask(ok, message, elapsedOverride, taskId = taskRuntime.displayedId) {
    const task = taskRuntime.active.get(taskId);
    if (!task) return false;
    if (task.timer) clearInterval(task.timer);
    const elapsed = elapsedOverride == null ? (Date.now() - task.startedAt) / 1000 : Number(elapsedOverride);
    const rawMessage = String(message || (ok ? "Complete" : "Failed")).trim();
    const finalMessage = withDuration(rawMessage, elapsed);
    taskRuntime.active.delete(taskId);
    logEvent(ok ? "ok" : "error", finalMessage, ok ? {} : { dedupeKey: rawMessage });
    if (taskRuntime.displayedId === taskId) {
      const next = [...taskRuntime.active.keys()].pop();
      if (next == null) {
        taskRuntime.displayedId = null;
        hideTaskCard();
      } else {
        taskRuntime.displayedId = next;
        paintTask(taskRuntime.active.get(next));
      }
    }
    return true;
  }

  function failTask(error, taskId) {
    const message = error instanceof Error ? error.message : String(error || "Request failed");
    endTask(false, message, undefined, taskId);
    showError(message);
    return message;
  }

  function setActionState(btn, enabled, reason = "") {
    if (!btn) return;
    btn.disabled = !enabled;
    const text = String(reason || "");
    btn.dataset.tip = enabled ? "" : text;
    btn.setAttribute(ACTION_TIP_ATTRIBUTE, enabled ? "" : text);
    btn.title = enabled ? "" : text;
    if (enabled) {
      btn.removeAttribute("aria-label");
    } else if (text) {
      btn.setAttribute("aria-label", text);
    }
  }

  function refreshActionStates() {
    const hasProject = state.selectedProjectId != null;
    const hasScreenplay = state.selectedScreenplayId != null;
    const hasScenes = state.scenes.length > 0;
    const pipelineReason = !hasScreenplay
      ? "Select a screenplay first."
      : state.pipelineInProgress
        ? "Pipeline is already running…"
        : "";
    setActionState(els.btnFullPipeline, hasScreenplay && !state.pipelineInProgress, pipelineReason);
    setActionState(els.btnDetect, hasScreenplay && !state.pipelineInProgress, pipelineReason);

    let generateAllReason = "";
    if (!hasScenes) {
      generateAllReason = "No scenes detected — run the pipeline first.";
    } else if (state.shotGenerationInProgress || state.shotsLoading) {
      generateAllReason = "Generating shots — please wait…";
    }
    setActionState(els.btnGenerateAll, hasScenes && !state.shotGenerationInProgress && !state.shotsLoading, generateAllReason);

    for (const button of $$('[data-shot-generate="true"]')) {
      const sceneId = String(button.dataset.sceneId);
      const busy = state.shotGenerationInProgress || String(state.activeShotSceneId) === sceneId;
      setActionState(button, !busy, busy ? "Generating shots — please wait…" : "");
    }

    const projectConstraintReason = !hasProject
      ? "Select a project first."
      : state.projectConstraintSaveInProgress || state.projectConstraintResetInProgress
        ? "Saving constraints — please wait…"
        : "";
    setActionState(
      els.saveProjectConstraints,
      hasProject && !state.projectConstraintSaveInProgress && !state.projectConstraintResetInProgress,
      projectConstraintReason,
    );
    setActionState(
      els.resetProjectConstraints,
      hasProject && !state.projectConstraintSaveInProgress && !state.projectConstraintResetInProgress,
      projectConstraintReason,
    );

    for (const button of $$('[data-scene-constraint-submit="true"]')) {
      const key = String(button.dataset.sceneId);
      const busy = String(state.sceneConstraintSaveInProgress) === key;
      setActionState(button, hasProject && !busy, hasProject ? (busy ? "Saving constraints — please wait…" : "") : "Select a project first.");
    }

    els.uploadForm.hidden = !hasProject;
    setActionState(els.uploadBtn, true);
    els.pipelineNote.textContent = hasScreenplay
      ? "Detect scenes, analyze the script, and extract film metadata."
      : "Select a screenplay to detect scenes, analyze the script, and extract film metadata.";
    if (els.projectCount) els.projectCount.textContent = String(state.projects.length);
    if (els.screenplayCount) els.screenplayCount.textContent = String(state.screenplays.length);
  }

  function renderEmptyState(element, { title, detail, ctaLabel, ctaHandler } = {}) {
    if (!element) return;
    element.textContent = "";
    if (!title) {
      element.hidden = true;
      return;
    }
    const heading = document.createElement("strong");
    heading.className = "empty-state-title";
    heading.textContent = title;
    element.appendChild(heading);
    if (detail) {
      const description = document.createElement("span");
      description.className = "empty-state-detail";
      description.textContent = detail;
      element.appendChild(description);
    }
    if (ctaLabel && ctaHandler) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn ghost";
      button.textContent = ctaLabel;
      button.addEventListener("click", ctaHandler);
      element.appendChild(button);
    }
    element.hidden = false;
  }

  function focusScreenplayList() {
    const first = els.screenplayList.querySelector(".entry-item");
    if (first) {
      first.focus();
      return;
    }
    if (state.selectedProjectId != null) {
      els.screenplayFile.focus();
      return;
    }
    els.projectName.focus();
  }

  function focusProjectForm() {
    els.projectName.focus();
  }

  function highlightSelected(list, selectedId) {
    for (const item of list.querySelectorAll(".entry-item")) {
      const selected = sameId(item.dataset.entryId, selectedId);
      item.classList.toggle("is-selected", selected);
      item.setAttribute("aria-pressed", String(selected));
    }
  }

  function renderProjects() {
    els.projectList.textContent = "";
    els.projectEmpty.hidden = state.projects.length > 0;
    if (!state.projects.length) els.projectEmpty.textContent = "No projects yet. Create one to begin.";
    for (const project of state.projects) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "entry-item";
      button.dataset.entryId = String(project.id);
      button.innerHTML = `<span class="entry-from">${escapeHtml(project.name)}</span>`;
      if (project.description) {
        button.innerHTML += `<span class="entry-meta">${escapeHtml(project.description)}</span>`;
      }
      button.addEventListener("click", () => void selectProject(project.id));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "entry-delete";
      remove.textContent = "✕";
      remove.setAttribute("aria-label", `Delete project "${project.name}"`);
      remove.addEventListener("click", (event) => {
        event.stopPropagation();
        void deleteProject(project);
      });
      item.append(button, remove);
      els.projectList.appendChild(item);
    }
    highlightSelected(els.projectList, state.selectedProjectId);
    refreshActionStates();
  }

  async function deleteProject(project) {
    if (!window.confirm(`Delete project "${project.name}" and all its data?`)) return;
    const taskId = startTask(`Deleting project "${project.name}"…`);
    try {
      await api(`/projects/${project.id}`, { method: "DELETE" });
      state.projects = state.projects.filter((item) => !sameId(item.id, project.id));
      if (sameId(state.selectedProjectId, project.id)) {
        state.selectedProjectId = null;
        state.screenplays = [];
        state.selectedScreenplayId = null;
        state.scenes = [];
        state.scenesLoadedFor = null;
        state.screenplaysLoadedFor = null;
        state.screenplaysLoadingFor = null;
        state.projectConstraints = null;
        state.projectConstraintsLoaded = false;
        state.sceneConstraintsLoaded = {};
        state.sceneEffectiveConstraints = {};
        state.projectConstraintsLoading = false;
        resetShotState();
        fillConstraintForm(els.projectConstraintsForm, {});
        els.screenplayNote.textContent = "Select a project first.";
      }
      renderProjects();
      renderScreenplays();
      renderScreenplayMeta();
      renderScenes();
      renderShotScenes();
      renderSceneConstraints();
      refreshActionStates();
      endTask(true, `Project "${project.name}" deleted`, undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    }
  }

  function renderScreenplays() {
    els.screenplayList.textContent = "";
    const hasScreenplays = state.screenplays.length > 0;
    els.screenplayEmpty.hidden = hasScreenplays;
    if (!hasScreenplays) {
      if (state.screenplaysLoadingFor) {
        els.screenplayEmpty.textContent = "Loading screenplays…";
      } else if (state.selectedProjectId == null) {
        els.screenplayEmpty.textContent = "Select a project first.";
      } else {
        els.screenplayEmpty.textContent = "No screenplays in this project yet. Upload one below.";
      }
    }
    for (const screenplay of state.screenplays) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "entry-item";
      button.dataset.entryId = String(screenplay.id);
      button.innerHTML = `<span class="entry-from">${escapeHtml(screenplay.filename)}</span><span class="entry-meta">.${escapeHtml(screenplay.format)} — ${escapeHtml(formatDate(screenplay.created_at))}${screenplay.analyzed ? " — metadata ready" : ""}</span>`;
      button.addEventListener("click", () => void selectScreenplay(screenplay.id));
      item.appendChild(button);
      els.screenplayList.appendChild(item);
    }
    highlightSelected(els.screenplayList, state.selectedScreenplayId);
    refreshActionStates();
  }

  function renderScreenplayMeta() {
    els.screenplayMeta.textContent = "";
    const screenplay = state.screenplays.find((item) => sameId(item.id, state.selectedScreenplayId));
    if (!screenplay) {
      renderEmptyState(els.screenplayMetaEmpty, {
        title: "No screenplay selected.",
        detail: "Choose a screenplay in the left rail to see its metadata.",
        ctaLabel: "Choose a screenplay",
        ctaHandler: focusScreenplayList,
      });
      return;
    }
    els.screenplayMetaEmpty.hidden = true;
    const meta = document.createElement("div");
    meta.className = "meta-block";
    meta.innerHTML = `<div><strong>One-liner:</strong> ${escapeHtml(screenplay.one_liner ?? "—")}</div><div><strong>Genre:</strong> ${escapeHtml(screenplay.genre ?? "—")}</div><div><strong>Story abstract:</strong> ${escapeHtml(screenplay.story_abstract ?? "—")}</div><div><strong>Characters:</strong> ${escapeHtml(asArray(screenplay.characters).join(", ") || "—")}</div>`;
    els.screenplayMeta.appendChild(meta);
    if (!screenplay.analyzed) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn ghost";
      button.textContent = "Analyze screenplay";
      button.addEventListener("click", () => void analyzeScreenplay(screenplay));
      els.screenplayMeta.appendChild(button);
    } else {
      const tag = document.createElement("span");
      tag.className = "analyzed-tag";
      tag.textContent = "analyzed";
      els.screenplayMeta.appendChild(tag);
    }
  }

  function renderScenes() {
    els.sceneList.textContent = "";
    const hasScreenplay = state.selectedScreenplayId != null;
    const hasScenes = state.scenes.length > 0;
    if (!hasScreenplay) {
      renderEmptyState(els.sceneEmpty, {
        title: "Select a screenplay first.",
        detail: "Its detected scenes will appear here.",
        ctaLabel: "Choose a screenplay",
        ctaHandler: focusScreenplayList,
      });
      els.sceneNote.textContent = "Select a screenplay to see its detected scenes.";
    } else if (state.scenesLoading) {
      renderEmptyState(els.sceneEmpty, { title: "Reading scenes…" });
      els.sceneNote.textContent = "Loading the selected screenplay…";
    } else if (!hasScenes) {
      renderEmptyState(els.sceneEmpty, {
        title: "No scenes detected yet.",
        detail: "Run detection or the full pipeline to build the scene list.",
        ctaLabel: "Run the pipeline",
        ctaHandler: () => goToTab("pipeline"),
      });
      els.sceneNote.textContent = "No scenes detected in this screenplay.";
    } else {
      els.sceneEmpty.hidden = true;
      const screenplay = state.screenplays.find((item) => sameId(item.id, state.selectedScreenplayId));
      els.sceneNote.textContent = `${state.scenes.length} scene${state.scenes.length === 1 ? "" : "s"} detected${screenplay ? ` in “${screenplay.filename}”` : ""}.`;
    }

    for (const [index, scene] of state.scenes.entries()) {
      const details = document.createElement("details");
      details.className = "scene";
      details.dataset.sceneId = String(scene.id);
      const summary = document.createElement("summary");
      const number = scene.scene_number ?? index + 1;
      summary.innerHTML = `<span class="scene-number">${escapeHtml(number)}</span><span class="scene-heading">${escapeHtml(scene.heading || `Scene ${number}`)}</span><span class="scene-slug">${escapeHtml(scene.location ?? "")}${scene.time_of_day ? " — " + escapeHtml(scene.time_of_day) : ""}</span>`;
      const pre = document.createElement("pre");
      pre.textContent = scene.raw_text ?? "";
      details.append(summary, pre);
      if (scene.analyzed) {
        const meta = document.createElement("div");
        meta.className = "scene-meta";
        meta.innerHTML = `<div class="meta-block"><strong>Characters:</strong> ${escapeHtml(asArray(scene.characters).join(", "))}</div><div class="meta-block"><strong>Actions:</strong> ${escapeHtml(asArray(scene.actions).join(" | "))}</div><div class="meta-block"><strong>Dialogue:</strong> ${escapeHtml(asArray(scene.dialogue).join(" | "))}</div>${scene.narrative_context ? `<div class="meta-block"><strong>Context:</strong> ${escapeHtml(scene.narrative_context)}</div>` : ""}<span class="analyzed-tag">analyzed</span>`;
        details.appendChild(meta);
      } else {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn ghost scene-analyze-btn";
        button.textContent = "Analyze scene";
        button.addEventListener("click", () => void analyzeScene(scene));
        details.appendChild(button);
      }
      els.sceneList.appendChild(details);
    }
    refreshActionStates();
  }

  function renderWarnings(container, warnings) {
    if (!container) return;
    container.textContent = "";
    const values = asArray(warnings).map((warning) => String(warning)).filter(Boolean);
    if (!values.length) {
      container.hidden = true;
      return;
    }
    const list = document.createElement("ul");
    list.className = "shot-warning-list";
    for (const warning of values) {
      const item = document.createElement("li");
      item.textContent = warning;
      list.appendChild(item);
    }
    container.appendChild(list);
    container.hidden = false;
  }

  function appendShotChip(parent, label, value) {
    const chip = document.createElement("span");
    chip.className = "shot-chip";
    const chipLabel = document.createElement("span");
    chipLabel.className = "shot-chip-label";
    chipLabel.textContent = label;
    const chipValue = document.createElement("span");
    chipValue.className = "shot-chip-value";
    chipValue.textContent = value == null || value === "" ? "—" : String(value);
    chip.append(chipLabel, chipValue);
    parent.appendChild(chip);
  }

  function appendShotText(parent, label, value) {
    if (value == null || value === "") return;
    const line = document.createElement("p");
    line.className = "shot-text";
    const strong = document.createElement("strong");
    strong.textContent = `${label}: `;
    line.append(strong, document.createTextNode(String(value)));
    parent.appendChild(line);
  }

  function renderShots(sceneId, shots) {
    const container = [...els.shotSceneList.querySelectorAll("[data-shot-container-for]")].find(
      (item) => item.dataset.shotContainerFor === String(sceneId),
    );
    if (!container) return;
    container.textContent = "";
    const values = Array.isArray(shots) ? shots : [];
    if (!values.length) {
      const empty = document.createElement("p");
      empty.className = "empty-state shot-empty-inline";
      empty.textContent = "No shots generated yet.";
      container.appendChild(empty);
      return;
    }
    for (const shot of values) {
      const card = document.createElement("article");
      card.className = "shot-card";
      const head = document.createElement("div");
      head.className = "shot-card-head";
      const ref = document.createElement("span");
      ref.className = "shot-ref";
      ref.textContent = shot.ref || `Scene ${shot.scene_number ?? ""} - Shot ${shot.shot_number ?? ""}`;
      const status = document.createElement("span");
      const statusText = String(shot.status || "draft").toLowerCase();
      status.className = `analyzed-tag shot-status is-${statusText === "approved" ? "approved" : "draft"}`;
      status.textContent = statusText;
      head.append(ref, status);
      const meta = document.createElement("div");
      meta.className = "shot-meta";
      appendShotChip(meta, "Type", shot.shot_type);
      appendShotChip(meta, "Angle", shot.camera_angle);
      appendShotChip(meta, "Lens", shot.lens);
      appendShotChip(meta, "Movement", shot.camera_movement);
      appendShotChip(meta, "Duration", shot.duration == null ? null : `${shot.duration}s`);
      card.append(head, meta);
      appendShotText(card, "Characters", asArray(shot.characters).join(", "));
      appendShotText(card, "Action", shot.action);
      appendShotText(card, "Visual description", shot.visual_description);
      appendShotText(card, "Dialogue", shot.dialogue);
      appendShotText(card, "Continuity", shot.continuity_notes);
      appendShotText(card, "Director notes", shot.director_notes);
      container.appendChild(card);
    }
  }

  function renderShotScenes() {
    els.shotSceneList.textContent = "";
    renderWarnings(els.shotWarnings, []);
    const hasScreenplay = state.selectedScreenplayId != null;
    const hasScenes = state.scenes.length > 0;
    if (!hasScreenplay) {
      renderEmptyState(els.shotEmpty, {
        title: "Select a screenplay first.",
        detail: "Choose a screenplay before generating a shot plan.",
        ctaLabel: "Choose a screenplay",
        ctaHandler: focusScreenplayList,
      });
      refreshActionStates();
      return;
    }
    if (state.shotsLoading) {
      renderEmptyState(els.shotEmpty, { title: "Loading shots…" });
      refreshActionStates();
      return;
    }
    if (!hasScenes) {
      renderEmptyState(els.shotEmpty, {
        title: "No scenes detected yet.",
        detail: "Run the pipeline first, then return here to generate coverage.",
        ctaLabel: "Run the pipeline",
        ctaHandler: () => goToTab("pipeline"),
      });
      refreshActionStates();
      return;
    }
    els.shotEmpty.hidden = true;
    const collectiveWarnings = [];
    for (const [index, scene] of state.scenes.entries()) {
      const key = String(scene.id);
      const shots = state.shotsByScene[key] ?? [];
      const number = scene.scene_number ?? index + 1;
      const details = document.createElement("details");
      details.className = "scene shot-scene";
      details.dataset.sceneId = key;
      const summary = document.createElement("summary");
      summary.innerHTML = `<span class="scene-number">${escapeHtml(number)}</span><span class="scene-heading">${escapeHtml(scene.heading || `Scene ${number}`)}</span>`;
      const count = document.createElement("span");
      count.className = "shot-count";
      count.textContent = `${shots.length} shot${shots.length === 1 ? "" : "s"}`;
      summary.appendChild(count);
      details.appendChild(summary);

      const actions = document.createElement("div");
      actions.className = "shot-actions";
      const generateButton = document.createElement("button");
      generateButton.type = "button";
      generateButton.className = "btn ghost";
      generateButton.dataset.shotGenerate = "true";
      generateButton.dataset.sceneId = key;
      generateButton.textContent = "Generate shots";
      const replaceLabel = document.createElement("label");
      replaceLabel.className = "checkbox-label";
      const replaceInput = document.createElement("input");
      replaceInput.type = "checkbox";
      replaceInput.className = "scene-replace";
      replaceInput.setAttribute("aria-label", "Replace existing drafts");
      replaceLabel.append(replaceInput, document.createTextNode(" Replace existing drafts"));
      generateButton.addEventListener("click", () => void generateShotsForScene(scene, replaceInput));
      actions.append(generateButton, replaceLabel);
      details.appendChild(actions);

      const warnings = document.createElement("div");
      warnings.className = "scene-warnings";
      renderWarnings(warnings, state.shotWarningsByScene[key] ?? []);
      for (const warning of state.shotWarningsByScene[key] ?? []) {
        collectiveWarnings.push(`Scene ${number}: ${warning}`);
      }
      details.appendChild(warnings);
      const shotContainer = document.createElement("div");
      shotContainer.className = "shot-cards";
      shotContainer.dataset.shotContainerFor = key;
      details.appendChild(shotContainer);
      els.shotSceneList.appendChild(details);
      renderShots(scene.id, shots);
    }
    renderWarnings(els.shotWarnings, collectiveWarnings);
    refreshActionStates();
  }

  function normalizeConstraintValue(value) {
    if (Array.isArray(value)) {
      return value.map((item) => String(item).trim()).filter(Boolean).sort().join("|") || null;
    }
    if (typeof value === "string") return value.trim() || null;
    return value ?? null;
  }

  function constraintValuesEqual(left, right) {
    return normalizeConstraintValue(left) === normalizeConstraintValue(right);
  }

  function fillConstraintForm(form, values = {}, projectValues = null, includeOverrides = false) {
    if (!form) return;
    const source = values ?? {};
    const project = projectValues ?? {};
    for (const field of CONSTRAINT_FIELDS) {
      const value = source[field] ?? null;
      if (field === "camera_movement_allowed") {
        const valuesForField = Array.isArray(value)
          ? value
          : typeof value === "string"
            ? value.split(",")
            : [];
        for (const checkbox of form.querySelectorAll(`input[type="checkbox"][data-constraint-field="${field}"]`)) {
          checkbox.checked = valuesForField.some((item) => String(item).trim() === checkbox.value);
        }
      } else if (field === "available_lenses") {
        const input = form.querySelector(`[data-constraint-field="${field}"]`);
        if (input) input.value = Array.isArray(value) ? value.join(", ") : value == null ? "" : String(value);
      } else if (BOOLEAN_CONSTRAINT_FIELDS.has(field)) {
        const checkbox = form.querySelector(`[data-constraint-field="${field}"]`);
        if (checkbox) checkbox.checked = value === true;
      } else {
        const input = form.querySelector(`[data-constraint-field="${field}"]`);
        if (input) input.value = value == null ? "" : String(value);
      }
      if (includeOverrides) {
        const override = form.querySelector(`[data-override-field="${field}"]`);
        if (override) override.checked = !constraintValuesEqual(value, project[field] ?? null);
      }
    }
  }

  function readConstraintValue(form, field, preserveEmptyList = false) {
    if (BOOLEAN_CONSTRAINT_FIELDS.has(field)) {
      const checkbox = form.querySelector(`[data-constraint-field="${field}"]`);
      return checkbox ? checkbox.checked : null;
    }
    if (field === "camera_movement_allowed") {
      const values = [...form.querySelectorAll(`input[type="checkbox"][data-constraint-field="${field}"]:checked`)].map((checkbox) => checkbox.value);
      return values.length ? values : preserveEmptyList ? [] : null;
    }
    if (field === "available_lenses") {
      const input = form.querySelector(`[data-constraint-field="${field}"]`);
      const values = (input?.value ?? "").split(",").map((value) => value.trim()).filter(Boolean);
      return values.length ? values : preserveEmptyList ? [] : null;
    }
    const input = form.querySelector(`[data-constraint-field="${field}"]`);
    return input?.value.trim() || null;
  }

  function serializeConstraintForm(form, overridesOnly = false) {
    const body = {};
    for (const field of CONSTRAINT_FIELDS) {
      const override = overridesOnly ? form.querySelector(`[data-override-field="${field}"]`) : null;
      body[field] = overridesOnly && (!override || !override.checked) ? null : readConstraintValue(form, field, overridesOnly);
    }
    return body;
  }

  function constraintOverrideMarkup(field) {
    return `<label class="constraint-override"><input type="checkbox" data-override-field="${field}"> Override</label>`;
  }

  function constraintFieldMarkup(field, label, { wide = false, override = false, type = "text" } = {}) {
    const className = `constraint-field${wide ? " constraint-field-wide" : ""}`;
    const head = `<div class="constraint-field-head"><span class="field-label">${escapeHtml(label)}</span>${override ? constraintOverrideMarkup(field) : ""}</div>`;
    if (field === "camera_movement_allowed") {
      return `<fieldset class="${className}"><legend class="field-label">${escapeHtml(label)}</legend>${override ? constraintOverrideMarkup(field) : ""}<div class="choice-grid">${CAMERA_MOVEMENTS.map((movement) => `<label class="choice-label"><input type="checkbox" name="${field}" data-constraint-field="${field}" value="${escapeHtml(movement)}"> ${escapeHtml(movement)}</label>`).join("")}</div></fieldset>`;
    }
    if (BOOLEAN_CONSTRAINT_FIELDS.has(field)) {
      const labelText = field === "high_angle_possible" ? "High angle" : "Low angle";
      return `<div class="${className}">${head}<div class="choice-grid"><label class="choice-label"><input type="checkbox" name="${field}" data-constraint-field="${field}"> ${labelText}</label></div></div>`;
    }
    const input = type === "textarea"
      ? `<textarea name="${field}" data-constraint-field="${field}" rows="4"></textarea>`
      : `<input type="text" name="${field}" data-constraint-field="${field}">`;
    return `<div class="${className}">${head}${input}</div>`;
  }

  function createSceneConstraintForm(sceneId) {
    const form = document.createElement("form");
    form.className = "constraint-form scene-constraint-form";
    form.dataset.constraintForm = "scene";
    form.dataset.sceneId = String(sceneId);
    form.innerHTML = `<div class="constraint-grid">${constraintFieldMarkup("location_constraints", "Location constraints", { override: true })}${constraintFieldMarkup("available_lenses", "Available lenses (comma-separated)", { override: true })}${constraintFieldMarkup("camera_movement_allowed", "Camera movement allowed", { wide: true, override: true })}${constraintFieldMarkup("high_angle_possible", "High angle possible", { override: true })}${constraintFieldMarkup("low_angle_possible", "Low angle possible", { override: true })}${constraintFieldMarkup("equipment_constraints", "Equipment constraints", { override: true })}${constraintFieldMarkup("director_preferences", "Director preferences", { override: true })}${constraintFieldMarkup("additional_notes", "Additional notes", { wide: true, override: true, type: "textarea" })}</div><div class="constraint-actions"><button type="submit" class="btn primary" data-scene-constraint-submit="true" data-scene-id="${escapeHtml(sceneId)}">Save scene constraints</button></div>`;
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const scene = state.scenes.find((item) => sameId(item.id, sceneId));
      if (scene) void saveSceneConstraints(scene);
    });
    return form;
  }

  function renderSceneConstraints() {
    els.sceneConstraintsList.textContent = "";
    const hasProject = state.selectedProjectId != null;
    const hasScenes = state.scenes.length > 0;
    if (!hasProject) {
      renderEmptyState(els.sceneConstraintsEmpty, {
        title: "Select a project first.",
        detail: "Project constraints become available after you choose a project.",
        ctaLabel: "Create a project",
        ctaHandler: focusProjectForm,
      });
      refreshActionStates();
      return;
    }
    if (!hasScenes) {
      renderEmptyState(els.sceneConstraintsEmpty, {
        title: "No scenes detected yet.",
        detail: "Scene-specific overrides appear after the pipeline creates a scene list.",
        ctaLabel: "Run the pipeline",
        ctaHandler: () => goToTab("pipeline"),
      });
      refreshActionStates();
      return;
    }
    els.sceneConstraintsEmpty.hidden = true;
    for (const [index, scene] of state.scenes.entries()) {
      const key = String(scene.id);
      const number = scene.scene_number ?? index + 1;
      const details = document.createElement("details");
      details.className = "constraints-panel scene-constraint-card";
      details.dataset.sceneConstraintsId = key;
      const summary = document.createElement("summary");
      summary.innerHTML = `<span class="scene-number">${escapeHtml(number)}</span><span class="scene-heading">${escapeHtml(scene.heading || `Scene ${number}`)}</span><span class="scene-slug">${state.sceneConstraintsLoaded[key] ? "Override loaded" : "Load effective values"}</span>`;
      const form = createSceneConstraintForm(scene.id);
      if (state.sceneConstraintsLoaded[key]) {
        fillConstraintForm(form, state.sceneEffectiveConstraints[key], state.projectConstraints, true);
      } else {
        fillConstraintForm(form, state.projectConstraints ?? {}, state.projectConstraints ?? {}, true);
      }
      details.append(summary, form);
      details.addEventListener("toggle", () => {
        if (details.open) void loadSceneConstraintsForm(details, scene.id);
      });
      els.sceneConstraintsList.appendChild(details);
    }
    refreshActionStates();
  }

  async function loadProjectConstraints() {
    if (state.selectedProjectId == null) {
      renderSceneConstraints();
      return;
    }
    if (state.projectConstraintsLoaded || state.projectConstraintsLoading) {
      renderSceneConstraints();
      return;
    }
    const projectId = state.selectedProjectId;
    state.projectConstraintsLoading = true;
    renderSceneConstraints();
    const taskId = startTask("Loading project constraints");
    try {
      const data = await api(`/projects/${projectId}/constraints`);
      if (!sameId(state.selectedProjectId, projectId)) {
        endTask(true, "Project selection changed", undefined, taskId);
        return;
      }
      state.projectConstraints = data;
      state.projectConstraintsLoaded = true;
      fillConstraintForm(els.projectConstraintsForm, data);
      renderSceneConstraints();
      endTask(true, "Project constraints loaded", undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    } finally {
      if (sameId(state.selectedProjectId, projectId)) state.projectConstraintsLoading = false;
      refreshActionStates();
    }
  }

  async function loadSceneConstraintsForm(detailsEl, sceneId) {
    const key = String(sceneId);
    if (state.sceneConstraintsLoaded[key]) {
      const form = detailsEl.querySelector("[data-constraint-form]");
      if (form) fillConstraintForm(form, state.sceneEffectiveConstraints[key], state.projectConstraints, true);
      return;
    }
    if (state.selectedProjectId == null) {
      refreshActionStates();
      return;
    }
    const projectId = state.selectedProjectId;
    const scene = state.scenes.find((item) => sameId(item.id, sceneId));
    const sceneNumber = scene?.scene_number ?? sceneId;
    const taskId = startTask(`Loading constraints for scene ${sceneNumber}`);
    try {
      const projectData = state.projectConstraints ?? (await api(`/projects/${projectId}/constraints`));
      if (!sameId(state.selectedProjectId, projectId)) {
        endTask(true, "Project selection changed", undefined, taskId);
        return;
      }
      if (!state.projectConstraintsLoaded) {
        state.projectConstraints = projectData;
        state.projectConstraintsLoaded = true;
        fillConstraintForm(els.projectConstraintsForm, projectData);
      }
      const sceneData = await api(`/projects/${projectId}/scenes/${sceneId}/constraints`);
      if (!sameId(state.selectedProjectId, projectId)) {
        endTask(true, "Project selection changed", undefined, taskId);
        return;
      }
      const form = detailsEl.querySelector("[data-constraint-form]");
      if (form) fillConstraintForm(form, sceneData, projectData, true);
      state.sceneEffectiveConstraints[key] = sceneData;
      state.sceneConstraintsLoaded[key] = true;
      renderSceneConstraints();
      endTask(true, `Scene ${sceneNumber} constraints loaded`, undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    } finally {
      refreshActionStates();
    }
  }

  async function loadSceneConstraintsForScenes() {
    if (state.selectedProjectId == null || state.scenes.length === 0) {
      renderSceneConstraints();
      return;
    }
    renderSceneConstraints();
    for (const scene of [...state.scenes]) {
      const details = [...els.sceneConstraintsList.querySelectorAll("[data-scene-constraints-id]")].find(
        (item) => item.dataset.sceneConstraintsId === String(scene.id),
      );
      if (details) await loadSceneConstraintsForm(details, scene.id);
    }
  }

  async function saveProjectConstraints() {
    if (state.selectedProjectId == null) return;
    const projectId = state.selectedProjectId;
    state.projectConstraintSaveInProgress = true;
    refreshActionStates();
    const taskId = startTask("Saving project constraints");
    try {
      const data = await api(
        `/projects/${projectId}/constraints`,
        jsonRequest("PUT", serializeConstraintForm(els.projectConstraintsForm)),
      );
      if (!sameId(state.selectedProjectId, projectId)) {
        endTask(true, "Project selection changed", undefined, taskId);
        return;
      }
      state.projectConstraints = data;
      state.projectConstraintsLoaded = true;
      state.sceneConstraintsLoaded = {};
      state.sceneEffectiveConstraints = {};
      fillConstraintForm(els.projectConstraintsForm, data);
      renderSceneConstraints();
      endTask(true, "Project constraints saved", undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    } finally {
      if (sameId(state.selectedProjectId, projectId)) state.projectConstraintSaveInProgress = false;
      refreshActionStates();
    }
  }

  async function resetProjectConstraints() {
    if (state.selectedProjectId == null) return;
    const projectId = state.selectedProjectId;
    state.projectConstraintResetInProgress = true;
    refreshActionStates();
    const taskId = startTask("Resetting project constraints");
    const defaults = {
      location_constraints: null,
      camera_movement_allowed: null,
      high_angle_possible: null,
      low_angle_possible: null,
      available_lenses: null,
      equipment_constraints: null,
      director_preferences: null,
      additional_notes: null,
    };
    try {
      const data = await api(`/projects/${projectId}/constraints`, jsonRequest("PUT", defaults));
      if (!sameId(state.selectedProjectId, projectId)) {
        endTask(true, "Project selection changed", undefined, taskId);
        return;
      }
      state.projectConstraints = data;
      state.projectConstraintsLoaded = true;
      state.sceneConstraintsLoaded = {};
      state.sceneEffectiveConstraints = {};
      fillConstraintForm(els.projectConstraintsForm, data);
      renderSceneConstraints();
      endTask(true, "Project constraints reset", undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    } finally {
      if (sameId(state.selectedProjectId, projectId)) state.projectConstraintResetInProgress = false;
      refreshActionStates();
    }
  }

  async function saveSceneConstraints(scene) {
    if (state.selectedProjectId == null) return;
    const key = String(scene.id);
    const formElement = [...els.sceneConstraintsList.querySelectorAll("[data-constraint-form='scene']")].find(
      (form) => form.dataset.sceneId === key,
    );
    if (!formElement) {
      showError("Open the scene constraints form before saving.");
      return;
    }
    const projectId = state.selectedProjectId;
    state.sceneConstraintSaveInProgress = key;
    refreshActionStates();
    const taskId = startTask(`Saving constraints for scene ${scene.scene_number ?? scene.id}`);
    try {
      const data = await api(
        `/projects/${projectId}/scenes/${scene.id}/constraints`,
        jsonRequest("PUT", serializeConstraintForm(formElement, true)),
      );
      state.sceneEffectiveConstraints[key] = data;
      state.sceneConstraintsLoaded[key] = true;
      if (state.projectConstraints) fillConstraintForm(formElement, data, state.projectConstraints, true);
      renderSceneConstraints();
      endTask(true, `Scene ${scene.scene_number ?? scene.id} constraints saved`, undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    } finally {
      if (String(state.sceneConstraintSaveInProgress) === key) state.sceneConstraintSaveInProgress = null;
      refreshActionStates();
    }
  }

  async function consumeSse(response, { onProgress, onComplete, onError } = {}) {
    if (!response.ok) {
      let message = `HTTP ${response.status}`;
      try {
        const data = await response.json();
        if (data?.detail) message = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      } catch (error) {
        message = `HTTP ${response.status}`;
      }
      throw new Error(message);
    }
    if (!response.body) throw new Error("Streaming response has no body.");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const processFrame = (raw) => {
      const normalized = raw.replace(/\r\n/g, "\n").trim();
      if (!normalized) return;
      const lines = normalized.split("\n");
      const eventType = lines.find((line) => line.startsWith("event:"))?.slice(6).trim() || "message";
      const dataLines = lines.filter((line) => line.startsWith("data:"));
      if (!dataLines.length) return;
      let data;
      try {
        data = JSON.parse(dataLines.map((line) => line.slice(5).trim()).join("\n"));
      } catch (error) {
        throw new Error("The stream returned invalid JSON.");
      }
      if (eventType === "progress" && onProgress) onProgress(data);
      if (eventType === "complete" && onComplete) onComplete(data);
      if (eventType === "error") {
        const message = data.message || "Stream request failed.";
        if (onError) onError(message);
        throw new Error(message);
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        buffer = buffer.replace(/\r\n/g, "\n");
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";
        for (const raw of frames) processFrame(raw);
      }
      buffer += decoder.decode();
      processFrame(buffer);
    } finally {
      reader.releaseLock();
    }
  }

  function resetShotState() {
    state.shotsByScene = {};
    state.shotWarningsByScene = {};
    state.sceneConstraintsLoaded = {};
    state.sceneEffectiveConstraints = {};
    state.shotsLoadedFor = null;
    els.shotSceneList.textContent = "";
    renderWarnings(els.shotWarnings, []);
  }

  async function generateShotsForScene(scene, replaceInput) {
    if (state.shotGenerationInProgress || (state.activeShotSceneId != null && String(state.activeShotSceneId) !== String(scene.id))) return;
    const key = String(scene.id);
    state.activeShotSceneId = key;
    refreshActionStates();
    const taskId = startTask(`Generating shots for scene ${scene.scene_number ?? scene.id}`);
    try {
      updateTask(10, "Sending scene to the shot generator…", taskId);
      const data = await api(
        "/shots/generate",
        jsonRequest("POST", {
          scene_id: scene.id,
          replace_existing: Boolean(replaceInput?.checked),
        }),
      );
      state.shotsByScene[key] = asArray(data.shots);
      state.shotWarningsByScene[key] = asArray(data.warnings);
      state.shotsLoadedFor = state.selectedScreenplayId;
      updateTask(100, "Shots generated.", taskId);
      renderShotScenes();
      endTask(true, `Shots generated for scene ${scene.scene_number ?? scene.id}`, undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    } finally {
      if (String(state.activeShotSceneId) === key) state.activeShotSceneId = null;
      refreshActionStates();
    }
  }

  async function generateAllShots() {
    if (state.shotGenerationInProgress) return;
    const screenplay = state.screenplays.find((item) => sameId(item.id, state.selectedScreenplayId));
    if (!screenplay || state.scenes.length === 0) return;
    state.shotGenerationInProgress = true;
    refreshActionStates();
    const taskId = startTask(`Generating shots for all scenes in “${screenplay.filename}”`);
    let completed = false;
    try {
      const response = await fetch(`/screenplays/${screenplay.id}/generate-shots-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ replace_existing: Boolean(els.batchReplace.checked) }),
      });
      await consumeSse(response, {
        onProgress: (data) => updateTask(data.percent ?? null, data.detail || data.step || "", taskId),
        onComplete: (data) => {
          if (!sameId(state.selectedScreenplayId, screenplay.id)) {
            endTask(true, "Screenplay selection changed", undefined, taskId);
            completed = true;
            return;
          }
          const nextWarnings = {};
          const collectiveWarnings = [];
          for (const plan of asArray(data.plans)) {
            const key = String(plan.scene_id);
            state.shotsByScene[key] = asArray(plan.shots);
            nextWarnings[key] = asArray(plan.warnings);
            const scene = state.scenes.find((item) => sameId(item.id, plan.scene_id));
            const sceneNumber = scene?.scene_number ?? plan.scene_number ?? key;
            collectiveWarnings.push(...asArray(plan.warnings).map((warning) => `Scene ${sceneNumber}: ${warning}`));
          }
          state.shotWarningsByScene = nextWarnings;
          state.shotsLoadedFor = screenplay.id;
          updateTask(100, "Shots generated.", taskId);
          renderShotScenes();
          renderWarnings(els.shotWarnings, collectiveWarnings);
          endTask(true, "Shots generated for all scenes", undefined, taskId);
          completed = true;
        },
        onError: (message) => {
          endTask(false, message, undefined, taskId);
          showError(message);
        },
      });
      if (!completed) endTask(true, "Shots generated for all scenes", undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    } finally {
      state.shotGenerationInProgress = false;
      refreshActionStates();
    }
  }

  async function runDetection(sp) {
    await runLlmAction(sp, `/screenplays/${sp.id}/detect-scenes`, "Scene detection complete");
  }

  async function runFullPipeline(sp) {
    if (state.pipelineInProgress) return;
    state.pipelineInProgress = true;
    refreshActionStates();
    const taskId = startTask(`Running full pipeline for “${sp.filename}”`);
    let completed = false;
    try {
      const query = els.pipelineGenerateShots.checked ? "?generate_shots=true" : "?generate_shots=false";
      const response = await fetch(`/screenplays/${sp.id}/full-pipeline-stream${query}`, { method: "POST" });
      await consumeSse(response, {
        onProgress: (data) => updateTask(data.percent ?? null, data.detail || data.step || "", taskId),
        onComplete: (data) => {
          if (sameId(state.selectedScreenplayId, sp.id)) {
            state.scenes = asArray(data.scenes);
            state.scenesLoadedFor = sp.id;
            state.screenplaysLoadingFor = null;
            if (data.screenplay) {
              const index = state.screenplays.findIndex((item) => sameId(item.id, sp.id));
              if (index !== -1) state.screenplays[index] = data.screenplay;
            }
            resetShotState();
            renderScreenplays();
            renderScenes();
            renderScreenplayMeta();
            renderShotScenes();
          }
          updateTask(100, "Pipeline complete.", taskId);
          endTask(true, "Full pipeline complete", undefined, taskId);
          completed = true;
        },
        onError: (message) => {
          endTask(false, message, undefined, taskId);
          showError(message);
        },
      });
      if (!completed) endTask(true, "Full pipeline complete", undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    } finally {
      state.pipelineInProgress = false;
      refreshActionStates();
    }
  }

  async function runLlmAction(sp, path, doneText) {
    const taskId = startTask(`Running ${doneText.toLowerCase()} for “${sp.filename}”`);
    try {
      updateTask(25, "Sending request…", taskId);
      const data = await api(path, { method: "POST" });
      if (sameId(state.selectedScreenplayId, sp.id)) {
        state.scenes = asArray(data.scenes);
        state.scenesLoadedFor = sp.id;
        resetShotState();
        renderScenes();
        renderShotScenes();
        const index = state.screenplays.findIndex((item) => sameId(item.id, sp.id));
        if (index !== -1) {
          const refreshed = await api(`/screenplays/${sp.id}`);
          state.screenplays[index] = refreshed;
          renderScreenplays();
          renderScreenplayMeta();
        }
      }
      updateTask(100, doneText, taskId);
      endTask(true, doneText, undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    }
  }

  async function analyzeScreenplay(sp) {
    const taskId = startTask(`Analyzing “${sp.filename}”`);
    try {
      updateTask(30, "Extracting screenplay metadata…", taskId);
      const data = await api(`/screenplays/${sp.id}/analyze`, { method: "POST" });
      const index = state.screenplays.findIndex((item) => sameId(item.id, data.id));
      if (index !== -1) state.screenplays[index] = data;
      renderScreenplays();
      renderScreenplayMeta();
      updateTask(100, "Screenplay analysis complete.", taskId);
      endTask(true, "Screenplay analysis complete", undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    }
  }

  async function analyzeScene(scene) {
    const taskId = startTask(`Analyzing scene ${scene.scene_number ?? scene.id}`);
    try {
      updateTask(30, "Extracting scene structure…", taskId);
      const data = await api(`/scenes/${scene.id}/analyze`, { method: "POST" });
      const index = state.scenes.findIndex((item) => sameId(item.id, data.id));
      if (index !== -1) state.scenes[index] = data;
      renderScenes();
      updateTask(100, "Scene analysis complete.", taskId);
      endTask(true, `Scene ${scene.scene_number ?? scene.id} analysis complete`, undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    }
  }

  async function selectProject(id) {
    const projectKey = String(id);
    if (sameId(state.selectedProjectId, id) && state.screenplaysLoadedFor === projectKey) {
      renderProjects();
      renderScreenplays();
      renderScreenplayMeta();
      renderScenes();
      renderShotScenes();
      renderSceneConstraints();
      refreshActionStates();
      return;
    }
    if (state.screenplaysLoadingFor === projectKey) return;
    state.selectedProjectId = id;
    state.screenplays = [];
    state.selectedScreenplayId = null;
    state.scenes = [];
    state.scenesLoadedFor = null;
    state.screenplaysLoadedFor = null;
    state.screenplaysLoadingFor = projectKey;
    state.projectConstraints = null;
    state.projectConstraintsLoaded = false;
    state.sceneConstraintsLoaded = {};
    state.sceneEffectiveConstraints = {};
    state.projectConstraintsLoading = false;
    resetShotState();
    fillConstraintForm(els.projectConstraintsForm, {});
    const project = state.projects.find((item) => sameId(item.id, id));
    els.screenplayNote.textContent = project ? `Screenplays in “${project.name}”.` : "Select a project first.";
    renderProjects();
    renderScreenplays();
    renderScreenplayMeta();
    renderScenes();
    renderShotScenes();
    renderSceneConstraints();
    const taskId = startTask(`Loading screenplays for “${project?.name || "project"}”`);
    try {
      const data = await api(`/screenplays/projects/${id}`);
      if (!sameId(state.selectedProjectId, id)) {
        endTask(true, "Project selection changed", undefined, taskId);
        return;
      }
      state.screenplays = asArray(data);
      state.screenplaysLoadedFor = projectKey;
      renderScreenplays();
      endTask(true, "Screenplays loaded", undefined, taskId);
    } catch (error) {
      if (sameId(state.selectedProjectId, id)) {
        state.screenplays = [];
        renderScreenplays();
        failTask(error, taskId);
      } else {
        endTask(true, "Project selection changed", undefined, taskId);
      }
    } finally {
      if (state.screenplaysLoadingFor === projectKey) state.screenplaysLoadingFor = null;
      renderScreenplays();
      refreshActionStates();
    }
  }

  async function selectScreenplay(id) {
    const screenplayKey = String(id);
    if (sameId(state.selectedScreenplayId, id) && state.scenesLoadedFor === screenplayKey) {
      renderScreenplays();
      renderScreenplayMeta();
      renderScenes();
      renderShotScenes();
      refreshActionStates();
      return;
    }
    if (state.scenesLoading && sameId(state.selectedScreenplayId, id)) return;
    state.selectedScreenplayId = id;
    state.scenes = [];
    state.scenesLoadedFor = null;
    state.scenesLoading = true;
    state.shotsLoadedFor = null;
    resetShotState();
    const screenplay = state.screenplays.find((item) => sameId(item.id, id));
    els.sceneNote.textContent = screenplay ? `Scenes detected in “${screenplay.filename}”.` : "Select a screenplay to see its detected scenes.";
    renderScreenplays();
    renderScreenplayMeta();
    renderScenes();
    renderShotScenes();
    const taskId = startTask(`Loading scenes from “${screenplay?.filename || "screenplay"}”`);
    try {
      const data = await api(`/screenplays/${id}/scenes`);
      if (!sameId(state.selectedScreenplayId, id)) {
        endTask(true, "Screenplay selection changed", undefined, taskId);
        return;
      }
      state.scenes = asArray(data.scenes);
      state.scenesLoadedFor = screenplayKey;
      els.sceneNote.textContent = `${data.total_scenes ?? state.scenes.length} scene${(data.total_scenes ?? state.scenes.length) === 1 ? "" : "s"} detected${screenplay ? ` in “${screenplay.filename}”` : ""}.`;
      renderScenes();
      renderShotScenes();
      endTask(true, "Scenes loaded", undefined, taskId);
    } catch (error) {
      if (sameId(state.selectedScreenplayId, id)) {
        state.scenes = [];
        renderScenes();
        renderShotScenes();
        failTask(error, taskId);
      } else {
        endTask(true, "Screenplay selection changed", undefined, taskId);
      }
    } finally {
      if (sameId(state.selectedScreenplayId, id)) state.scenesLoading = false;
      renderScenes();
      renderShotScenes();
      refreshActionStates();
      if (state.activeTab === "shots") void loadShotsForScenes();
      if (state.activeTab === "constraints") {
        void loadProjectConstraints();
        void loadSceneConstraintsForScenes();
      }
    }
  }

  async function loadProjects() {
    const taskId = startTask("Loading projects");
    try {
      const data = await api("/projects");
      state.projects = asArray(data);
      renderProjects();
      if (state.projects.length === 1 && !sameId(state.selectedProjectId, state.projects[0].id)) {
        await selectProject(state.projects[0].id);
      }
      endTask(true, "Projects loaded", undefined, taskId);
    } catch (error) {
      renderProjects();
      els.projectEmpty.textContent = "Could not load projects.";
      failTask(error, taskId);
    } finally {
      refreshActionStates();
    }
  }

  async function onProjectCreate(event) {
    event.preventDefault();
    const name = els.projectName.value.trim();
    if (!name) return;
    const description = els.projectDesc.value.trim() || null;
    const button = els.projectForm.querySelector("button[type='submit']");
    setActionState(button, false, "Creating project…");
    const taskId = startTask(`Creating project “${name}”`);
    try {
      await api("/projects", jsonRequest("POST", { name, description }));
      els.projectName.value = "";
      els.projectDesc.value = "";
      await loadProjects();
      const created = [...state.projects].reverse().find((project) => project.name === name);
      if (created) {
        await selectProject(created.id);
        goToTab("pipeline");
      }
      endTask(true, "Project created", undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    } finally {
      setActionState(button, true);
      refreshActionStates();
    }
  }

  async function onUpload(event) {
    event.preventDefault();
    const file = els.screenplayFile.files[0];
    if (state.selectedProjectId == null || !file) return;
    const projectId = state.selectedProjectId;
    const formData = new FormData();
    formData.append("file", file);
    setActionState(els.uploadBtn, false, "Uploading screenplay…");
    const taskId = startTask(`Uploading “${file.name}”`);
    try {
      updateTask(15, "Uploading screenplay…", taskId);
      const data = await api(`/screenplays/projects/${projectId}/upload`, {
        method: "POST",
        body: formData,
      });
      if (!sameId(state.selectedProjectId, projectId)) {
        endTask(true, "Project selection changed", undefined, taskId);
        return;
      }
      state.screenplays.push(data);
      state.screenplaysLoadedFor = String(projectId);
      els.screenplayFile.value = "";
      if (els.filePicker) els.filePicker.textContent = "Choose screenplay…";
      await selectScreenplay(data.id);
      goToTab("scenes");
      updateTask(100, "Upload complete.", taskId);
      endTask(true, "Screenplay uploaded", undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    } finally {
      setActionState(els.uploadBtn, true);
      refreshActionStates();
    }
  }

  function renderHealth(data) {
    const llm = data?.llm ?? {};
    const embeddings = data?.embeddings ?? {};
    els.healthText.textContent = `${llm.provider || "unknown"} — ${llm.model || "unknown model"}`;
    if (embeddings.provider && embeddings.provider !== "ollama") els.healthText.textContent += ` · embeddings: ${embeddings.provider}`;
    if (llm.provider) els.llmProvider.value = llm.provider;
    if (embeddings.provider) els.embedProvider.value = embeddings.provider;
    els.healthChip.classList.add("is-ok");
    els.healthChip.classList.remove("is-error");
    state.health = data;
  }

  async function loadHealth() {
    const taskId = startTask("Checking provider health");
    try {
      const data = await api("/health");
      renderHealth(data);
      endTask(true, "Provider health checked", undefined, taskId);
    } catch (error) {
      els.healthText.textContent = "health check failed";
      els.healthChip.classList.remove("is-ok");
      els.healthChip.classList.add("is-error");
      failTask(error, taskId);
    }
  }

  async function switchProvider(which, value) {
    const taskId = startTask(`Switching ${which === "llm" ? "LLM" : "embedding"} provider`);
    try {
      const body = which === "llm" ? { llm_provider: value } : { embedding_provider: value };
      const status = await api("/providers", jsonRequest("POST", body));
      renderHealth(status);
      endTask(true, "Provider updated", undefined, taskId);
    } catch (error) {
      failTask(error, taskId);
    }
  }

  async function pingProviders() {
    const taskId = startTask("Pinging providers");
    setActionState(els.pingBtn, false, "Pinging providers…");
    els.pingBtn.textContent = "Pinging…";
    try {
      const data = await api("/providers/ping", { method: "POST" });
      const errors = [];
      const latencies = [];
      if (data.llm.latency_ms != null) latencies.push(`LLM ${data.llm.latency_ms}ms`);
      else errors.push(`LLM: ${data.llm.error || "failed"}`);
      if (data.embeddings.latency_ms != null) latencies.push(`embeddings ${data.embeddings.latency_ms}ms`);
      else errors.push(`embeddings: ${data.embeddings.error || "failed"}`);
      if (state.health) renderHealth(state.health);
      if (latencies.length) els.healthText.textContent += ` · ping ${latencies.join(" · ")}`;
      els.healthChip.classList.toggle("is-ok", !errors.length);
      if (errors.length) {
        const message = `Ping failed — ${errors.join(" · ")}`;
        endTask(false, message, undefined, taskId);
        showError(message);
      } else {
        endTask(true, "Providers responded", undefined, taskId);
      }
    } catch (error) {
      failTask(error, taskId);
    } finally {
      setActionState(els.pingBtn, true);
      els.pingBtn.textContent = "Ping";
    }
  }

  function goToTab(name) {
    const target = name || "pipeline";
    state.activeTab = target;
    for (const tab of $$(".tab")) {
      const active = tab.dataset.tab === target;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    }
    for (const panel of $$("[data-tab-panel]")) {
      const active = panel.dataset.tabPanel === target;
      panel.classList.toggle("is-active", active);
      panel.hidden = !active;
      panel.setAttribute("aria-hidden", String(!active));
    }
    if (target === "pipeline") {
      renderScreenplayMeta();
    } else if (target === "scenes") {
      renderScenes();
    } else if (target === "shots") {
      renderShotScenes();
      void loadShotsForScenes();
    } else if (target === "constraints") {
      renderSceneConstraints();
      void loadProjectConstraints();
      void loadSceneConstraintsForScenes();
    }
    refreshActionStates();
  }

  async function loadShotsForScenes() {
    if (state.shotGenerationInProgress) return;
    if (state.selectedScreenplayId == null || state.scenes.length === 0) {
      renderShotScenes();
      return;
    }
    if (state.shotsLoadedFor != null && sameId(state.shotsLoadedFor, state.selectedScreenplayId) && !state.shotsLoading) {
      renderShotScenes();
      return;
    }
    const screenplayId = state.selectedScreenplayId;
    const scenes = [...state.scenes];
    state.shotsLoading = true;
    state.shotsByScene = {};
    state.shotWarningsByScene = {};
    renderShotScenes();
    refreshActionStates();
    const taskId = startTask("Loading existing shots");
    let firstError = null;
    try {
      for (const scene of scenes) {
        const data = await api(`/scenes/${scene.id}/shots`);
        if (!sameId(state.selectedScreenplayId, screenplayId)) {
          endTask(true, "Screenplay selection changed", undefined, taskId);
          return;
        }
        state.shotsByScene[String(scene.id)] = asArray(data);
      }
      state.shotsLoadedFor = screenplayId;
      updateTask(100, "Shots loaded.", taskId);
      renderShotScenes();
      endTask(true, "Shots loaded", undefined, taskId);
    } catch (error) {
      firstError = error instanceof Error ? error.message : String(error);
      if (sameId(state.selectedScreenplayId, screenplayId)) {
        renderShotScenes();
        failTask(error, taskId);
      } else {
        endTask(true, "Screenplay selection changed", undefined, taskId);
      }
    } finally {
      state.shotsLoading = false;
      if (firstError && sameId(state.selectedScreenplayId, screenplayId)) {
        els.shotEmpty.hidden = false;
      }
      refreshActionStates();
    }
  }

  hydrateActivity();
  els.projectForm.addEventListener("submit", onProjectCreate);
  els.uploadForm.addEventListener("submit", onUpload);
  els.projectConstraintsForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void saveProjectConstraints();
  });
  els.resetProjectConstraints.addEventListener("click", () => void resetProjectConstraints());
  els.btnGenerateAll.addEventListener("click", () => void generateAllShots());
  els.llmProvider.addEventListener("change", (event) => void switchProvider("llm", event.target.value));
  els.embedProvider.addEventListener("change", (event) => void switchProvider("embeddings", event.target.value));
  els.pingBtn.addEventListener("click", () => void pingProviders());
  els.screenplayFile.addEventListener("change", () => {
    const file = els.screenplayFile.files[0];
    if (els.filePicker) els.filePicker.textContent = file ? file.name : "Choose screenplay…";
  });
  for (const tab of $$(".tab")) {
    tab.addEventListener("click", () => goToTab(tab.dataset.tab));
  }
  els.settingsToggle.addEventListener("click", () => {
    const open = els.settingsPanel.hidden;
    els.settingsPanel.hidden = !open;
    els.settingsToggle.setAttribute("aria-expanded", String(open));
  });
  els.btnDetect.addEventListener("click", () => {
    const screenplay = state.screenplays.find((item) => sameId(item.id, state.selectedScreenplayId));
    if (screenplay) void runDetection(screenplay);
  });
  els.btnFullPipeline.addEventListener("click", () => {
    const screenplay = state.screenplays.find((item) => sameId(item.id, state.selectedScreenplayId));
    if (screenplay) void runFullPipeline(screenplay);
  });

  renderProjects();
  renderScreenplays();
  renderScreenplayMeta();
  renderScenes();
  renderShotScenes();
  renderSceneConstraints();
  refreshActionStates();
  void loadProjects();
  void loadHealth();
})();
