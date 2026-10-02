# OneShot — Development Status

> Last updated: 2026-09-25
> Current phase: **Phase 4 — Scene to Shot Segmentation (DONE)**
> Next phase: **Phase 5 — Shot Editing and Validation**

This file is a temporary, living log of project development status. It is
updated after each phase milestone and whenever a significant issue or
decision occurs. `docs/plan.md` is the task checklist; this file records where
we actually stand and what went wrong along the way.

---

## Phase Summary

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 1 | Backend Foundation | DONE | FastAPI app, SQLite/SQLModel, schemas, config, /health, projects CRUD, tests |
| 2 | Document to Scene Extraction | DONE | PDF/DOCX/TXT ingest, scene detection, persistence, services, API, tests |
| 3 | Structured Scene Understanding | DONE | LLM detection + typo tolerance, validated analysis, full pipeline, UI buttons, migration, tests |
| 4 | Scene to Shot Segmentation | DONE | Shot + ProductionConstraints models, generator, validation, continuity, constraint merge, endpoints, pipeline hook, tests |
| 5 | Shot Editing and Validation | NOT STARTED | — |
| 6 | Cinematic Knowledge / RAG | NOT STARTED | Mandatory, uses online/local provider |
| 7 | Storyboard Generation | NOT STARTED | — |
| 8 | Frontend | NOT STARTED | — |

---

## Phase Details

### Phase 1 — Backend Foundation (DONE)

Implemented:
- Project structure (`src/oneshot/`) with `api/`, `services/`, `parsers/`, `ai/`
- FastAPI app + lifespan DB init + `/health` endpoint
- SQLModel persistence models: `Project`, `Screenplay`, `Scene` (`db_models.py`)
- Pydantic API schemas incl. Shot enums (`schemas.py`)
- Config via env vars (`config.py`), SQLite setup (`db.py`)
- Projects CRUD: create, list, get

### Phase 2 — Document to Scene Extraction (DONE)

Implemented:
- PDF (PyMuPDF), DOCX (python-docx), TXT extractors behind unified `parsers/document.py`
- Scene heading detection + line classifier (heading/action/character/parenthetical/dialogue)
- Upload endpoint auto-extracts text and detects scenes
- Screenplay + scene persistence and retrieval endpoints
- Tests: parsers, scene detector, screenplay service, API

### Phase 3 — Structured Scene Understanding (DONE)

Implemented:
- LLM abstraction is provider-selectable: LiteRT (default, local) via the
  `litert_llm_service`/`embeddinggemma-service` HTTP services, plus Ollama,
  Gemini API, and Hugging Face as config-driven alternatives (`ai/llm.py`,
  config, `/health`); per-call provider override via `?provider=` query param
- LLM scene detection with typo tolerance + merging of new scenes into the
  regex-detected set, ordered by document position (`ai/scene_detector_llm.py`,
  `services/scene_service.detect_scenes_llm_and_merge`)
- Structured scene analysis returning validated Pydantic output
  (`SceneAnalysisResult`: characters/actions/dialogue/narrative_context) — spec §9
- `Scene` table columns via Alembic migration `5e95762f5fcc` (characters,
  actions, dialogue, narrative_context, analyzed)
- Endpoints: `POST /scenes/{scene_id}/analyze`, `GET /scenes/{scene_id}`,
  `POST /screenplays/{id}/detect-scenes`, `POST /screenplays/{id}/full-pipeline`
- Full-pipeline orchestration service (`services/pipeline_service.py`)
- Environment config: `.env` + `.env.example`, `python-dotenv`; `HF_TOKEN`
  configured by user for online dev path
- Temp UI updated: per-scene **Analyze**, per-screenplay **LLM Detection** and
  **Full Pipeline →** buttons, analyzed-data display, loading/error handling
- Tests: `tests/test_scene_analysis.py` (9 tests) — detection, typo tolerance,
  review for new scenes, targeted analysis, invalid JSON fallback,
  persistence, full pipeline, provider passthrough. Suite: 56 passed, ruff clean.

### Temp UI (minimal test bench) — YES

Per spec §12, a rough UI was added purely to make testing/demo easier. Not part of
Phase 8 (frontend).

- Static HTML/CSS/JS served by FastAPI at `/ui` (`src/oneshot/ui/`)
- Covers Phase 1–2 workflow: create/select project → upload screenplay
  (PDF/DOCX/TXT) → view detected scenes (expandable raw text)
- Header chip reads `/health` to show current LLM provider/model
- Zero new dependencies, no build step
- Tests: `tests/test_api_ui.py` (3 tests: index, assets, API non-regression)

### Phase 4 — Scene to Shot Segmentation (DONE)

Implemented:
- `Shot` + `ProductionConstraints` DB models; `Scene`/`Screenplay` character lists
  moved to JSON columns (migration `4e619e382aba`; sqlite needs `render_as_batch=True`)
- `ai/shot_generator.py` — calls LLM with injected JSON scene + constraints +
  schema, parses response, validates each shot against `AIShotData`
- `ai/llm.py.generate(..., json_schema=...)` threaded through all 4 providers
  (gemini response_schema, ollama json format, litert/HF json_object)
- `services/shot_service.py` — validation (enums, lens/movement vs constraints,
  character warnings, duration 1-120s), auto continuity notes between adjacent
  shots, persistence, effective (merged) constraints, batch generation w/ progress
- Constraint semantics: project defaults + per-scene field-level overrides; NULL
  columns mean "inherit"; violations excluded + reported in `warnings` (409 on
  re-generation unless `replace_existing=true`; approved shots never deleted)
- Endpoints: `POST /shots/generate`, `GET /shots/{shot_id}`,
  `GET /scenes/{scene_id}/shots`, `POST /screenplays/{id}/generate-shots` (+ SSE
  stream), `PUT`/`GET` project + scene constraints; full pipeline gained
  `generate_shots`
- Tests: shot generator, validation, continuity, constraint merge, shots API,
  constraints API, batch/stream, pipeline integration. Suite: 117 passed, ruff clean.
- Temp UI: **redesigned to a single-page workspace** (replaces the 5-step wizard)
  — project/screenplay picker left rail; Pipeline | Scenes | Shots | Constraints
  tabs; live **activity console** (current-task card with % and elapsed mm:ss
  timer + timestamped log, persisted to sessionStorage, SSE progress streams in
  real time); disabled buttons show an instant hover tooltip with the reason
  ("No scenes detected — run the pipeline first."); empty states get a contextual
  CTA. `/ui` assets now served with `Cache-Control: no-cache` via ASGI middleware
  to prevent stale `app.js`. (Verified live: /ui + assets 200 with no-cache.)

---
## Issues & Decisions Log

| Date | Phase | Area | Issue | Resolution |
|------|-------|------|-------|------------|
| 2026-09-12 | — | spec | RAG requirement level unclear | Decided: RAG is **mandatory** in shot generation; QLoRA fine-tuning is **optional**. Updated `docs/ONESHOT.md` + `docs/plan.md`. |
| 2026-09-12 | — | docs | `ONESHOT.md` / `plan.md` at root | Moved to `docs/` folder; `AGENTS.md` paths updated. |
| 2026-09-12 | 3 | ai | LLM layer only supported local Ollama; HuggingFace raised NotImplementedError | Implemented online HF provider (text + embeddings) and per-call provider choice. Dev uses HF online, deployment stays local Ollama (Gemma 4 E4B). |
| 2026-09-12 | 3 | config | HF "gemma-4-e4b" model id is a placeholder | Resolved 2026-09-13 — default is now `google/gemma-3-4b-it` on the Inference Providers router. |
| 2026-09-12 | 3 | config | Online provider requires secret | `HF_TOKEN` env var required; clear RuntimeError raised if missing. No secrets committed. |
| 2026-09-12 | 3 | config | No `.env` support; user could not set provider/token without editing code | Added `python-dotenv`, `load_dotenv()` in `config.py`, committed `.env.example` template, gitignored `.env`; user configured `HF_TOKEN`. |
| 2026-09-12 | — | ui | Testing backend via curl only was slow | Added minimal temp UI at `/ui` (Phase 1–2 workflow, health chip). Served by FastAPI, no build step (`tests/test_api_ui.py`). |
| 2026-09-12 | — | test | Async tests failed ("asyncio not supported") | Enabled `asyncio_mode = "auto"` in `pyproject.toml`. Test suite: 44 passed, ruff clean. |
| 2026-09-12 | 3 | api | `POST /scenes/analyze` accepts raw `text` string and returns hardcoded "todo" scene | Fixed — now `POST /scenes/{scene_id}/analyze`: runs analysis, validates, persists. |
| 2026-09-12 | 3 | db | `Scene` table lacks characters/actions/dialogue/narrative_context | Fixed — Alembic migration `5e95762f5fcc` adds columns; migration applied to dev DB. |
| 2026-09-12 | 3 | services | `scene_service.analyze` only delegates, no validation or DB write | Fixed — validates `SceneAnalysisResult` and persists to Scene row. |
| 2026-09-12 | 3 | ai | `scene_analyzer` returns raw dict, not validated Pydantic output | Fixed — `analyze_scene` returns validated `SceneAnalysisResult`. |
| 2026-09-12 | 3 | detect | LLM-recovered new scenes were indistinguishable from regex scenes | Fixed — detection returns `type:new/regex/none`; new scenes merged into DB ordered by first line. |
| 2026-09-13 | 3 | ui | Temp UI had no way to run LLM features | Fixed — per-scene Analyze + per-screenplay LLM Detection / Full Pipeline buttons with analyzed-data cards. |
| 2026-09-13 | 3 | test | Merge test failed: new scene (INT. OFFICE - DAY) sorted after existing scenes | Fixed — renumber/correct scenes by document position of first line. |
| 2026-09-13 | 3 | error | UI buttons returned 500 on any LLM failure | Root cause: `.env` model name (gemma4:4b) didn't match installed model; unhandled httpx errors bubbled as 500. Fixed: model name corrected, routes now map errors (NotFound=404, provider HTTP/connect errors=502, missing token=503) via `api/errors.py`. |
| 2026-09-13 | 3 | provider | Default provider switched to **Hugging Face online** (`LLM_PROVIDER=huggingface`) | Verified end-to-end (generate / detect-scenes / analyze / embed). Embeddings kept consistent at 768 dims. |
| 2026-09-13 | 3 | config | Legacy `api-inference.huggingface.co` is retired; `google/gemma-4-e4b` and old nomic embedding id are invalid | Migrated to the **Inference Providers router** (`https://router.huggingface.co`): chat via `/v1/chat/completions`, embeddings via `/hf-inference/models/{model}/pipeline/feature-extraction`. LLM default `google/gemma-3-4b-it` (gemma-4 models on the router are reasoning-heavy, unsuitable for strict JSON fields); embedding default `BAAI/bge-base-en-v1.5` (768-dim, matches nomic/nomic-embed-text). |
| 2026-09-13 | 3 | parse | LLM wraps JSON in markdown code fences | Added `ai/json_output.parse_json` used by scene detector + analyzer to strip fences before `json.loads`. |
| 2026-09-12 | 4/5/7 | api | Shot generate/update, export endpoints are stubs returning "todo" data | Shot generate + shot list/get implemented in Phase 4 (2026-09-24); update/delete/approve still open (Phase 5), export open (Phase 7). |
| 2026-09-24 | 4 | db | Shot + ProductionConstraints tables and JSON columns (Scene/Screenplay character lists) | Migration `4e619e382aba`; sqlite batch mode enabled (`render_as_batch=True`) because JSON column type alters need table rebuild. |
| 2026-09-24 | 4 | ai | LLM provider JSON output | `json_schema` threaded through all providers (gemini response_schema, ollama format=json, litert/HF response_format json_object) + Pydantic post-validation never bypassed. |
| 2026-09-24 | 4 | constraints | Partial per-scene override wiped project defaults (whole-row write + non-null defaults) | Nullable DB columns + `model_dump(exclude_unset=True)` writes + `_constraints_to_dict` skips NULLs; `effective_constraints` merges defaults → project → scene per field; GET endpoints return merged result. |
| 2026-09-24 | 4 | api | Fake 502 in `test_generate_shots_conflicts_without_replace` (missing LLM mock) | Added `_mock_shots(monkeypatch)` in the conflict test; suite 117 passed, ruff clean. |
| 2026-09-25 | 4 | ui/back | Constraint fields couldn't be "un-overridden" (nullable schema needed for inherit) | Made 4 `ProductionConstraints` fields nullable; temp UI step 5 "Shots" added (constraints forms, per-scene + batch generation via SSE, pipeline `generate_shots` toggle). Suite 120 passed, ruff clean. |
| 2026-09-25 | 4 | ui | User: buttons greyed out with no reason; no visibility into what the system is doing after clicking; wizard flow too hidden | **Redesigned temp UI to single-page workspace** (Pipeline/Scenes/Shots/Constraints tabs) with live activity console (task %, elapsed timer, SSE progress, history log persisted to sessionStorage) and hover tooltips on disabled buttons explaining why. `/ui` served with `Cache-Control: no-cache` (ASGI middleware) to stop stale-app.js confusion. Suite 121 passed, ruff clean. |
| 2026-09-25 | 4 | ui | Console showed `api is not defined (0.0s)` — whole UI broken after redesign | The `api()` fetch helper was accidentally dropped during the app.js rewrite (20+ call sites, no definition → ReferenceError). Restored verbatim next to `jsonRequest`; added a `test_api_ui` regression asserting `function api(` exists. Suite 122 passed, ruff clean. |

---

## Blockers

| Blocker | Blocks | Notes |
|---------|--------|-------|
| Qdrant not required yet | Phase 6 | RAG work needs Qdrant running locally or a test mock |

---

## Verification

- Environment: `uv` — symlink `.venv` via `uv sync` (deps from `pyproject.toml`); activate with `uv run`
- Test command: `uv run pytest`
- Lint command: `uv run ruff check src tests`
- Latest run: 122 passed, 2 warnings (deprecation), ruff clean (2026-09-25)
- Provider: default **LiteRT (local)** — Gemma 4 E2B (`gemma-4-E2B-it`) via `litert_llm_service` on `:8101`, EmbeddingGemma 300M via `embeddinggemma-service` on `:8100`.
- Verified end-to-end with live LiteRT services (2026-09-21): `/providers/ping` (LLM + embeddings), project → screenplay upload → full pipeline → 4/4 scenes analyzed → screenplay metadata extracted.