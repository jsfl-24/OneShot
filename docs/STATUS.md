# OneShot — Development Status

> Last updated: 2026-09-12
> Current phase: **Phase 3 — Structured Scene Understanding (IN PROGRESS)**

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
| 3 | Structured Scene Understanding | IN PROGRESS | LLM analyzer + provider choice done; endpoint, persistence, tests pending |
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

### Phase 3 — Structured Scene Understanding (IN PROGRESS)

Done:
- LLM abstraction now supports online (Hugging Face) and local (Ollama) choice
  for both text generation and RAG embeddings (`ai/llm.py`, config, `/health`)
- Scene analysis prompt defined (`ai/prompts.py`)
- Pydantic `Scene` schema with characters/actions/dialogue/narrative_context exists

Remaining (see Blockers):
- `POST /scenes/analyze` still a stub (hardcoded "todo" response)
- Scene table has no columns for analyzed data
- Literally nothing persists analysis results
- No DB migration for new Scene columns
- No analyzer/service/API tests

---

## Issues & Decisions Log

| Date | Phase | Area | Issue | Resolution |
|------|-------|------|-------|------------|
| 2026-09-12 | — | spec | RAG requirement level unclear | Decided: RAG is **mandatory** in shot generation; QLoRA fine-tuning is **optional**. Updated `docs/ONESHOT.md` + `docs/plan.md`. |
| 2026-09-12 | — | docs | `ONESHOT.md` / `plan.md` at root | Moved to `docs/` folder; `AGENTS.md` paths updated. |
| 2026-09-12 | 3 | ai | LLM layer only supported local Ollama; HuggingFace raised NotImplementedError | Implemented online HF provider (text + embeddings) and per-call provider choice. Dev uses HF online, deployment stays local Ollama (Gemma 4 E4B). |
| 2026-09-12 | 3 | config | HF "gemma-4-e4b" model id is a placeholder | Default `HF_LLM_MODEL=google/gemma-4-e4b` via env; confirm real model id before relying on online dev path. |
| 2026-09-12 | 3 | config | Online provider requires secret | `HF_TOKEN` env var required; clear RuntimeError raised if missing. No secrets committed. |
| 2026-09-12 | — | test | Async tests failed ("asyncio not supported") | Enabled `asyncio_mode = "auto"` in `pyproject.toml`. Test suite: 44 passed, ruff clean. |
| 2026-09-12 | 3 | api | `POST /scenes/analyze` accepts raw `text` string and returns hardcoded "todo" scene | OPEN — must accept `scene_id`, run analysis, validate, persist. |
| 2026-09-12 | 3 | db | `Scene` table lacks characters/actions/dialogue/narrative_context | OPEN — needs migration before analysis results can be stored. |
| 2026-09-12 | 3 | services | `scene_service.analyze` only delegates, no validation or DB write | OPEN — must validate + persist when Phase 3 is completed. |
| 2026-09-12 | 3 | ai | `scene_analyzer` returns raw dict, not validated Pydantic output | OPEN — return validated Pydantic per spec §9. |
| 2026-09-12 | 4/5/7 | api | Shot generate/update, export endpoints are stubs returning "todo" data | OPEN — will be implemented in Phases 4, 5, and 7. |

---

## Blockers

| Blocker | Blocks | Notes |
|---------|--------|-------|
| Scene table missing analyzed-data columns + migration | Phase 3, then Phase 4 | Analysis results have nowhere to persist |
| `/scenes/analyze` endpoint is a stub | Phase 3, then Phase 4 | Must accept `scene_id`, return validated + persisted data |
| No scene-analysis tests | Phase 3 | Analyzer/service/API must be tested before calling phase done |
| Qdrant not required yet | Phase 6 | RAG work needs Qdrant running locally or a test mock |

---

## Verification

- Test command: `python -m pytest`
- Lint command: `python -m ruff check src tests`
- Latest run: 44 passed, ruff clean (2026-09-12)