# OneShot Development Plan

> Authoritative task checklist derived from `ONESHOT.md`.
> Mark phases/tasks done as they are completed. Next phase should not start until the current one passes verification.

---

## Project Goal

Build a local-first, AI-assisted filmmaking pre-production system that ingests screenplays (PDF/DOCX/TXT), parses scenes, generates cinematic shot plans, validates them, optionally generates storyboard images, and exports production plans — all without requiring hosted AI services.

---

## Tech Stack

| Layer                        | Technology                                                                                                                                           |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Language                     | Python                                                                                                                                               |
| Env/Package Mgmt             | uv — virtualenv + dependency manager                                                                                                                |
| API Framework                | FastAPI                                                                                                                                              |
| Validation/Schemas           | Pydantic                                                                                                                                             |
| DB                           | SQLite via SQLModel                                                                                                                                  |
| PDF Extraction               | PyMuPDF                                                                                                                                              |
| DOCX Extraction              | python-docx                                                                                                                                          |
| Vector DB                    | Qdrant                                                                                                                                               |
| LLM (deployment)             | LiteRT local serving —**Gemma 4 E2B** (`litert_llm_service` on :8101)                                                                       |
| LLM (development)            | LiteRT local serving — Gemma 4 E2B (default`LLM_PROVIDER=litert`; Ollama/Gemma 4 E4B and Gemini API still available)                              |
| RAG Embeddings (deployment)  | EmbeddingGemma 300M via LiteRT (`embeddinggemma-service` on :8100)                                                                                 |
| RAG Embeddings (development) | EmbeddingGemma 300M via LiteRT (default`EMBEDDING_PROVIDER=litert`; Ollama `nomic-embed-text` and Gemini `gemini-embedding-2` still available) |
| Version Control              | Git + GitHub                                                                                                                                         |

---

## Architecture Rules (apply to ALL phases)

- [ ] API routes remain thin: `route -> service -> domain -> persistence -> AI layer`
- [ ] DB models (`db_models.py`) stay separate from Pydantic schemas (`schemas.py`)
- [ ] LLM calls are isolated behind `ai/llm.py` — never called directly from routes or services
- [ ] All AI output is structured JSON validated through Pydantic before persisting
- [ ] LLM never touches the database directly
- [ ] Every generated shot is validated before storage
- [ ] Errors surface clearly — no silent discards
- [ ] Each module has its own tests
- [ ] Privacy: no external AI/API calls by default

---

## Phase 1: Backend Foundation

**Status:** DONE

- [X] Establish project structure (`src/oneshot/` with `api/`, `services/`, `parsers/`, `ai/`)
- [X] Configure FastAPI app with lifespan (`main.py`)
- [X] Define SQLModel persistence models (`db_models.py`): Project, Screenplay, Scene
- [X] Define Pydantic API schemas (`schemas.py`): request/response models, enums (ShotType, CameraAngle, etc.)
- [X] Set up configuration via env vars (`config.py`): DB URL, LLM/embedding provider endpoints (LiteRT/Ollama/Gemini/HF), Qdrant URL
- [X] Set up SQLite database init (`db.py`)
- [X] Add `/health` endpoint
- [X] Add project CRUD API (`/projects`): create, list, get

---

## Phase 2: Document to Scene Extraction

**Status:** DONE

- [X] PDF extraction via PyMuPDF (`parsers/pdf.py`)
- [X] DOCX extraction via python-docx (`parsers/docx.py`)
- [X] Plain text extraction (`parsers/text.py`)
- [X] Unified document extractor (`parsers/document.py`)
- [X] Scene heading detection with regex (`parsers/scene_detector.py`)
- [X] Line-by-line classifier: heading, action, character, parenthetical, dialogue
- [X] Screenplay upload endpoint (`POST /screenplays/projects/{id}/upload`)
- [X] Auto-extract text + detect scenes on upload
- [X] Persist screenplay and scenes to DB
- [X] List/retrieve screenplays and scenes endpoints
- [X] Tests: document parsers, scene detector, screenplay service, API

---

## Phase 3: Structured Scene Understanding

**Status:** DONE

### Goals

Extract structured data from raw scene text using the LLM: characters, actions, dialogue, and narrative context.

### Tasks

- [X] Design and test the scene analysis prompt (`ai/prompts.py` — expand `SCENE_ANALYSIS_PROMPT`)
- [X] Define a Pydantic model for structured scene analysis output (characters, actions, dialogue, narrative_context)
- [X] Wire `ai/scene_analyzer.py` to return validated Pydantic output (not raw dict)
- [X] Implement `scene_service.py` — analyze scene, validate, return structured result
- [X] Flesh out `POST /scenes/{scene_id}/analyze` endpoint — accept scene_id, run analysis, return result
- [X] Persist analyzed scene data back to the Scene table (add columns: characters, actions, dialogue, narrative_context)
- [X] Generate a DB migration for the new Scene columns
- [X] Add tests: scene analyzer unit test, service test, API test
- [X] Verify end-to-end: upload screenplay -> detect scenes -> analyze a scene -> return structured data
- [X] LLM scene detection: new scenes recovered (typo tolerance) and merged, ordered by document position
- [X] `POST /screenplays/{id}/detect-scenes` and `POST /screenplays/{id}/full-pipeline` endpoints
- [X] Temp UI buttons: per-scene Analyze, per-screenplay LLM Detection / Full Pipeline
- [X] **Screenplay-level metadata extraction**: one-liner, genre, story_abstract, characters via `SCREENPLAY_ANALYSIS_PROMPT`
- [X] **New DB columns on Screenplay**: `one_liner`, `genre`, `story_abstract`, `characters`, `analyzed`
- [X] **New endpoint**: `POST /screenplays/{id}/analyze` for film metadata extraction
- [X] **Updated full-pipeline**: also extracts film metadata after scene analysis
- [X] **Scene detection regex tightening**: requires 2+ chars after INT/EXT prefix, rejects short/false headings
- [X] **LLM merge dedup**: filters invalid headings (no INT/EXT prefix or no dash), checks text overlap (70% threshold)
- [X] **Scene numbering**: sequential 1, 2, 3... across entire screenplay, `total_scenes` field in API response
- [X] **Updated ScreenplayResponse**: includes `one_liner`, `genre`, `story_abstract`, `characters`, `analyzed`

---

## Phase 4: Scene to Shot Segmentation

**Status:** COMPLETE (pending end-to-end manual verification with a live LLM)

### Goals

Generate a constraint-aware, cinematic shot list from a structured scene using the LLM.

### Tasks

- [X] Design and test the shot generation prompt (`ai/prompts.py` — expand `SHOT_GENERATION_PROMPT`)
- [X] Define `Shot` DB model in `db_models.py` with all fields per spec (shot_type, camera_angle, lens, movement, duration, characters, dialogue, action, visual_description, continuity_notes, director_notes, status)
- [X] Generate DB migration for Shot table
- [X] Define `ProductionConstraints` DB model for persisting constraints per project
- [X] Generate DB migration for ProductionConstraints table
- [X] Implement `shot_generator.py` — call LLM, parse response, validate against Pydantic `Shot` schema
- [X] Implement `shot_service.py` — orchestrate generation, validate each shot, persist to DB
- [X] Flesh out `POST /shots/generate` endpoint — accept scene_id + optional constraints, return validated shots
- [X] Ensure each shot links back to its scene (traceability)
- [X] Add tests: shot generator unit test, validation test, service test, API test
- [ ] Verify end-to-end: upload screenplay -> detect scenes -> analyze scene -> generate shots -> shots persisted

### Delivered endpoints (Phase 4)

- `POST /shots/generate` — generate shots for one scene (accepts `generate_shots` content + inline constraints + `language`)
- `GET /shots/{shot_id}` — retrieve one shot
- `GET /scenes/{scene_id}/shots` — list shots for a scene
- `POST /screenplays/{id}/generate-shots` — generate shots for all scenes (batch)
- `POST /screenplays/{id}/generate-shots-stream` — SSE variant with per-scene progress
- `PUT` / `GET /projects/{project_id}/constraints` — project-level production constraints
- `PUT` / `GET /projects/{project_id}/scenes/{scene_id}/constraints` — per-scene overrides; GET returns merged (effective) constraints
- Full pipeline (`run_full_pipeline` / SSE) gained a `generate_shots` flag with progress in the 60-95% band

### Phase 4 decisions (implemented)

- Shot identity: internal global int `id`; display reference `"Scene 01 - Shot 01"`
- Duration: LLM-suggested (2-12s), editable by filmmaker (no LLM auto-correction)
- Continuity: auto-generated notes comparing adjacent shots
- Prompt: hybrid — cinematic principles + enum guardrails; full JSON schema example injected; all injects are JSON (`{scene_json}`, `{constraints_json}`, `{schema_json}`)
- Structured output: Pydantic post-validation + provider JSON mode (`json_schema` threaded through all 4 providers)
- Constraints: project defaults + per-scene field-level overrides; NULL DB columns mean "inherit" (project -> scene merge in `effective_constraints`); applied via prompt injection + post-generation validation (violations excluded and reported in `warnings`, never silently discarded)
- Regeneration: `replace_existing=false` default -> 409 unless shots replaced; approved shots are never deleted (drafts only)
- Migration `4e619e382aba` also converts `Scene`/`Screenplay` list columns (characters, actions, dialogue) to JSON; sqlite needs `render_as_batch=True` in `alembic/env.py`

---

## Phase 5: Shot Editing and Validation

**Status:** NOT STARTED

### Goals

Full CRUD on shots with validation and status management (draft/approved).

### Tasks

- [ ] `GET /shots/{shot_id}` — retrieve a single shot
- [ ] `GET /scenes/{scene_id}/shots` — list all shots for a scene
- [ ] `PATCH /shots/{shot_id}` — update individual shot fields
- [ ] `PUT /shots/{shot_id}/reorder` — change shot order within a scene
- [ ] `DELETE /shots/{shot_id}` — remove a shot
- [ ] `POST /shots/{shot_id}/approve` — set status to approved
- [ ] Implement shot validation service: required fields, valid enums, duration > 0, scene reference exists
- [ ] Validate on every create/update — reject invalid shots with clear error messages
- [ ] Add tests for each endpoint and validation rule
- [ ] Verify: generate shots -> edit fields -> reorder -> approve -> retrieve

---

## Phase 6: Cinematic Knowledge / RAG

**Status:** NOT STARTED

### Goals

Enhance shot quality with cinematic knowledge retrieval. **RAG is mandatory** and must be integrated into the shot-generation pipeline. Implementation stays replaceable, but the pipeline is only complete with RAG enabled.

### Development vs. Deployment (RAG / LLM serving)

- **Default (local, privacy-first):** RAG and LLM serving run **fully local through LiteRT** — LLM via `litert_llm_service` (Gemma 4 E2B on `:8101`), embeddings via `embeddinggemma-service` (EmbeddingGemma 300M on `:8100`). No third-party hosted AI — screenplay privacy is preserved.
- **Alternatives (config-driven):** Ollama (Gemma 4 E4B, `nomic-embed-text`) for fully-local dev without the `.litertlm` runtime, or online providers (Gemini API via `google-genai`, Hugging Face Inference Providers router) as a development-time convenience. Provider choice does not change application or RAG code paths.
- The provider must be selected through configuration (`LLM_PROVIDER`, embeddings config) and must not change application or RAG code paths.

### Tasks

- [ ] Set up Qdrant client connection (configurable URL)
- [ ] Design cinematic knowledge schema (shot types, camera techniques, lens characteristics, movement semantics)
- [ ] Populate Qdrant with reference cinematic knowledge (seed data)
- [ ] Implement embedding generation — default `embeddinggemma-service` (EmbeddingGemma 300M via LiteRT); Ollama `nomic-embed-text` and Gemini `gemini-embedding-2` as alternatives
- [ ] Implement LLM serving — default `litert_llm_service` (Gemma 4 E2B via LiteRT); Ollama (Gemma 4 E4B) and online providers as alternatives
- [ ] Build RAG retrieval layer: given a scene context + desired shot attributes, retrieve relevant cinematic references
- [ ] Integrate RAG into shot generation prompt (augment with retrieved context)
- [ ] Shot generation must always use RAG context — no non-RAG fallback path
- [ ] Add tests for embedding, retrieval, and prompt augmentation

---

## Phase 7: Storyboard Generation

**Status:** NOT STARTED

### Goals

Generate storyboard prompts from approved shots and optionally generate images. Failures must not corrupt the shot plan.

### Tasks

- [ ] Define `StoryboardPrompt` and `StoryboardImage` DB models
- [ ] Generate DB migration
- [ ] Implement prompt builder: take approved shot -> generate image generation prompt
- [ ] Implement optional image generation (local model or placeholder)
- [ ] `POST /shots/{shot_id}/storyboard` — generate storyboard prompt for a shot
- [ ] `GET /shots/{shot_id}/storyboard` — retrieve storyboard for a shot
- [ ] Ensure storyboard failures are caught and logged without affecting shots
- [ ] Add tests

---

## Phase 8: Frontend

**Status:** NOT STARTED

### Goals

Build UI only after backend is stable. Prioritize core workflow over polish.

### Tasks

- [ ] Load `frontend-design` skill and establish design system (`DESIGN.md`)
- [ ] Project dashboard — list projects, create new project
- [ ] Screenplay upload view — drag-and-drop, format selection
- [ ] Scene browser — navigate scenes, view heading/location/raw text/analyzed data
- [ ] Shot list editor — view, edit, reorder, delete shots per scene
- [ ] Shot validation feedback — show errors/warnings inline
- [ ] Approval workflow — mark shots as approved
- [ ] Production constraints form — input and save constraints per project
- [ ] Export view — download JSON production plan
- [ ] Responsive layout, error states, loading states

---

## Definition of Done (Backend MVP)

The backend is ready for frontend when it can:

1. [ ] Ingest a screenplay document locally (PDF/DOCX/TXT)
2. [ ] Extract and persist screenplay text
3. [ ] Detect and persist scenes
4. [ ] Produce structured scene understanding (characters, actions, dialogue, context)
5. [ ] Generate a constraint-aware shot list augmented with RAG knowledge
6. [ ] Validate and persist shots safely
7. [ ] Allow shot data to be edited and approved through APIs
8. [ ] Run without requiring a hosted AI provider
9. [ ] Be tested module by module

---

## API Endpoint Checklist

| Endpoint                                   | Phase | Status |
| ------------------------------------------ | ----- | ------ |
| `GET /health`                            | 1     | DONE   |
| `POST /projects`                         | 1     | DONE   |
| `GET /projects`                          | 1     | DONE   |
| `GET /projects/{id}`                     | 1     | DONE   |
| `POST /screenplays/projects/{id}/upload` | 2     | DONE   |
| `GET /screenplays/projects/{id}`         | 2     | DONE   |
| `GET /screenplays/{id}`                  | 2     | DONE   |
| `GET /screenplays/{id}/scenes`           | 2     | DONE   |
| `POST /scenes/{id}/analyze`              | 3     | DONE   |
| `GET /scenes/{id}`                       | 3     | DONE   |
| `POST /screenplays/{id}/detect-scenes`   | 3     | DONE   |
| `POST /screenplays/{id}/full-pipeline`   | 3     | DONE   |
| `POST /screenplays/{id}/analyze`         | 3     | DONE   |
| `POST /shots/generate`                   | 4     | STUB   |
| `GET /shots/{id}`                        | 5     | TODO   |
| `GET /scenes/{id}/shots`                 | 5     | TODO   |
| `PATCH /shots/{id}`                      | 5     | STUB   |
| `PUT /shots/{id}/reorder`                | 5     | TODO   |
| `DELETE /shots/{id}`                     | 5     | TODO   |
| `POST /shots/{id}/approve`               | 5     | TODO   |
| `POST /shots/{id}/storyboard`            | 7     | TODO   |
| `GET /shots/{id}/storyboard`             | 7     | TODO   |
| `POST /projects/{id}/constraints`        | 4     | TODO   |
| `GET /projects/{id}/constraints`         | 4     | TODO   |
| `GET /export/json`                       | 7+    | STUB   |

---

## Notes

- **Never skip phases.** Complete and verify each before starting the next.
- **LLM is replaceable** — the final model is not permanently selected. Keep `ai/llm.py` as the single abstraction point.
- **QLoRA fine-tuning** is optional and only considered after the baseline pipeline works and has been evaluated.
- **RAG is mandatory** — cinematic knowledge retrieval must be part of the shot-generation pipeline; the pipeline is not complete without it.
- **LLM/RAG provider by environment** — **defaults to LiteRT** (fully local, privacy-first): LLM via `litert_llm_service` (Gemma 4 E2B), embeddings via `embeddinggemma-service` (EmbeddingGemma 300M). Ollama (Gemma 4 E4B, `nomic-embed-text`) and Gemini API/Hugging Face remain available alternatives. Provider selection is config-driven only.
- **Storyboard failures must not corrupt the shot plan.**
- **Privacy first** — no external AI/API calls unless the user explicitly configures them.
