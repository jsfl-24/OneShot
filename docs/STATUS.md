# OneShot — Development Status

> Last updated: 2026-09-13
> Current phase: **Phase 3 — Structured Scene Understanding (DONE)**
> Next phase: **Phase 4 — Scene to Shot Segmentation**

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
| 4 | Scene to Shot Segmentation | NOT STARTED | Blocked by Phase 3 completion |
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
- LLM abstraction supports online (Hugging Face) and local (Ollama) choice for
  text generation and RAG embeddings (`ai/llm.py`, config, `/health`); per-call
  provider override via `?provider=` query param on the new endpoints
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
| 2026-09-12 | 4/5/7 | api | Shot generate/update, export endpoints are stubs returning "todo" data | OPEN — will be implemented in Phases 4, 5, and 7. |

---

## Blockers

| Blocker | Blocks | Notes |
|---------|--------|-------|
| Qdrant not required yet | Phase 6 | RAG work needs Qdrant running locally or a test mock |

---

## Verification

- Test command: `python -m pytest`
- Lint command: `python -m ruff check src tests`
- Latest run: 60 passed, 2 warnings, ruff clean (2026-09-13)
- Provider: default Hugging Face (online) — `google/gemma-3-4b-it` / `BAAI/bge-base-en-v1.5`; `AI LLM` buttons verified end-to-end.