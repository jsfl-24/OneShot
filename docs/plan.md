# OneShot Development Plan

> Authoritative task checklist derived from `ONESHOT.md`.  
> Mark phases/tasks done as they are completed. Next phase should not start until the current one passes verification.

---

## Project Goal

Build a local-first, AI-assisted filmmaking pre-production system that ingests screenplays (PDF/DOCX/TXT), parses scenes, generates cinematic shot plans, validates them, optionally generates storyboard images, and exports production plans — all without requiring hosted AI services.

---

## Tech Stack

| Layer              | Technology                                 |
| ------------------ | ------------------------------------------ |
| Language           | Python                                     |
| Env/Package Mgmt   | uv — virtualenv + dependency manager        |
| API Framework      | FastAPI                                    |
| Validation/Schemas | Pydantic                                    |
| DB                 | SQLite via SQLModel                        |
| PDF Extraction     | PyMuPDF                                    |
| DOCX Extraction    | python-docx                                |
| Vector DB          | Qdrant                                     |
| LLM (deployment)   | Ollama via local serving — Gemma 4 E4B     |
| LLM (development)  | Gemini API via `google-genai` — `gemma-4-26b-a4b-it` (default; Ollama/Hugging Face still available) |
| RAG Embeddings (deployment) | Ollama (nomic-embed-text)          |
| RAG Embeddings (development) | Gemini API — `gemini-embedding-2` (Hugging Face `BAAI/bge-base-en-v1.5` still available) |
| Version Control    | Git + GitHub                               |

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

- [x] Establish project structure (`src/oneshot/` with `api/`, `services/`, `parsers/`, `ai/`)
- [x] Configure FastAPI app with lifespan (`main.py`)
- [x] Define SQLModel persistence models (`db_models.py`): Project, Screenplay, Scene
- [x] Define Pydantic API schemas (`schemas.py`): request/response models, enums (ShotType, CameraAngle, etc.)
- [x] Set up configuration via env vars (`config.py`): DB URL, LLM provider, Ollama/Qdrant URLs
- [x] Set up SQLite database init (`db.py`)
- [x] Add `/health` endpoint
- [x] Add project CRUD API (`/projects`): create, list, get

---

## Phase 2: Document to Scene Extraction

**Status:** DONE

- [x] PDF extraction via PyMuPDF (`parsers/pdf.py`)
- [x] DOCX extraction via python-docx (`parsers/docx.py`)
- [x] Plain text extraction (`parsers/text.py`)
- [x] Unified document extractor (`parsers/document.py`)
- [x] Scene heading detection with regex (`parsers/scene_detector.py`)
- [x] Line-by-line classifier: heading, action, character, parenthetical, dialogue
- [x] Screenplay upload endpoint (`POST /screenplays/projects/{id}/upload`)
- [x] Auto-extract text + detect scenes on upload
- [x] Persist screenplay and scenes to DB
- [x] List/retrieve screenplays and scenes endpoints
- [x] Tests: document parsers, scene detector, screenplay service, API

---

## Phase 3: Structured Scene Understanding

**Status:** DONE

### Goals
Extract structured data from raw scene text using the LLM: characters, actions, dialogue, and narrative context.

### Tasks
- [x] Design and test the scene analysis prompt (`ai/prompts.py` — expand `SCENE_ANALYSIS_PROMPT`)
- [x] Define a Pydantic model for structured scene analysis output (characters, actions, dialogue, narrative_context)
- [x] Wire `ai/scene_analyzer.py` to return validated Pydantic output (not raw dict)
- [x] Implement `scene_service.py` — analyze scene, validate, return structured result
- [x] Flesh out `POST /scenes/{scene_id}/analyze` endpoint — accept scene_id, run analysis, return result
- [x] Persist analyzed scene data back to the Scene table (add columns: characters, actions, dialogue, narrative_context)
- [x] Generate a DB migration for the new Scene columns
- [x] Add tests: scene analyzer unit test, service test, API test
- [x] Verify end-to-end: upload screenplay -> detect scenes -> analyze a scene -> return structured data
- [x] LLM scene detection: new scenes recovered (typo tolerance) and merged, ordered by document position
- [x] `POST /screenplays/{id}/detect-scenes` and `POST /screenplays/{id}/full-pipeline` endpoints
- [x] Temp UI buttons: per-scene Analyze, per-screenplay LLM Detection / Full Pipeline
- [x] **Screenplay-level metadata extraction**: one-liner, genre, story_abstract, characters via `SCREENPLAY_ANALYSIS_PROMPT`
- [x] **New DB columns on Screenplay**: `one_liner`, `genre`, `story_abstract`, `characters`, `analyzed`
- [x] **New endpoint**: `POST /screenplays/{id}/analyze` for film metadata extraction
- [x] **Updated full-pipeline**: also extracts film metadata after scene analysis
- [x] **Scene detection regex tightening**: requires 2+ chars after INT/EXT prefix, rejects short/false headings
- [x] **LLM merge dedup**: filters invalid headings (no INT/EXT prefix or no dash), checks text overlap (70% threshold)
- [x] **Scene numbering**: sequential 1, 2, 3... across entire screenplay, `total_scenes` field in API response
- [x] **Updated ScreenplayResponse**: includes `one_liner`, `genre`, `story_abstract`, `characters`, `analyzed`

---

## Phase 4: Scene to Shot Segmentation

**Status:** NOT STARTED

### Goals
Generate a constraint-aware, cinematic shot list from a structured scene using the LLM.

### Tasks
- [ ] Design and test the shot generation prompt (`ai/prompts.py` — expand `SHOT_GENERATION_PROMPT`)
- [ ] Define `Shot` DB model in `db_models.py` with all fields per spec (shot_type, camera_angle, lens, movement, duration, characters, dialogue, action, visual_description, continuity_notes, director_notes, status)
- [ ] Generate DB migration for Shot table
- [ ] Define `ProductionConstraints` DB model for persisting constraints per project
- [ ] Generate DB migration for ProductionConstraints table
- [ ] Implement `shot_generator.py` — call LLM, parse response, validate against Pydantic `Shot` schema
- [ ] Implement `shot_service.py` — orchestrate generation, validate each shot, persist to DB
- [ ] Flesh out `POST /shots/generate` endpoint — accept scene_id + optional constraints, return validated shots
- [ ] Ensure each shot links back to its scene (traceability)
- [ ] Add tests: shot generator unit test, validation test, service test, API test
- [ ] Verify end-to-end: upload screenplay -> detect scenes -> analyze scene -> generate shots -> shots persisted

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
- **Development:** RAG and LLM serving can use an **online model from Hugging Face via its online API** (preferred model: **Gemma 4 E4B**). This is a development-time convenience to iterate fast without a local inference server.
- **Deployment:** RAG and LLM serving must run **fully local** through **Ollama** (preferred model: **Gemma 4 E4B**, embeddings via `nomic-embed-text`). No third-party hosted AI in production — screenplay privacy is preserved.
- The provider must be selected through configuration (`LLM_PROVIDER`, embeddings config) and must not change application or RAG code paths.

### Tasks
- [ ] Set up Qdrant client connection (configurable URL)
- [ ] Design cinematic knowledge schema (shot types, camera techniques, lens characteristics, movement semantics)
- [ ] Populate Qdrant with reference cinematic knowledge (seed data)
- [ ] Implement embedding generation — Ollama `nomic-embed-text` for deployment, Hugging Face online embeddings API for development
- [ ] Implement LLM serving — Ollama (Gemma 4 E4B) for deployment, Hugging Face online API (Gemma 4 E4B) for development
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

| Endpoint                                    | Phase | Status  |
| ------------------------------------------- | ----- | ------- |
| `GET /health`                               | 1     | DONE    |
| `POST /projects`                            | 1     | DONE    |
| `GET /projects`                             | 1     | DONE    |
| `GET /projects/{id}`                        | 1     | DONE    |
| `POST /screenplays/projects/{id}/upload`    | 2     | DONE    |
| `GET /screenplays/projects/{id}`            | 2     | DONE    |
| `GET /screenplays/{id}`                     | 2     | DONE    |
| `GET /screenplays/{id}/scenes`       | 2     | DONE    |
| `POST /scenes/{id}/analyze`          | 3     | DONE    |
| `GET /scenes/{id}`                   | 3     | DONE    |
| `POST /screenplays/{id}/detect-scenes` | 3   | DONE    |
| `POST /screenplays/{id}/full-pipeline` | 3   | DONE    |
| `POST /screenplays/{id}/analyze`       | 3   | DONE    |
| `POST /shots/generate`                      | 4     | STUB    |
| `GET /shots/{id}`                           | 5     | TODO    |
| `GET /scenes/{id}/shots`                    | 5     | TODO    |
| `PATCH /shots/{id}`                         | 5     | STUB    |
| `PUT /shots/{id}/reorder`                   | 5     | TODO    |
| `DELETE /shots/{id}`                        | 5     | TODO    |
| `POST /shots/{id}/approve`                  | 5     | TODO    |
| `POST /shots/{id}/storyboard`               | 7     | TODO    |
| `GET /shots/{id}/storyboard`                | 7     | TODO    |
| `POST /projects/{id}/constraints`           | 4     | TODO    |
| `GET /projects/{id}/constraints`            | 4     | TODO    |
| `GET /export/json`                          | 7+    | STUB    |

---

## Notes

- **Never skip phases.** Complete and verify each before starting the next.
- **LLM is replaceable** — the final model is not permanently selected. Keep `ai/llm.py` as the single abstraction point.
- **QLoRA fine-tuning** is optional and only considered after the baseline pipeline works and has been evaluated.
- **RAG is mandatory** — cinematic knowledge retrieval must be part of the shot-generation pipeline; the pipeline is not complete without it.
- **LLM/RAG provider by environment** — development defaults to the Gemini API (`gemma-4-26b-a4b-it` via `google-genai`, needs `GEMINI_API_KEY`); Ollama (Gemma 4 E4B, `nomic-embed-text`) and Hugging Face Inference Providers remain available alternatives. Provider selection is config-driven only.
- **Storyboard failures must not corrupt the shot plan.**
- **Privacy first** — no external AI/API calls unless the user explicitly configures them.
