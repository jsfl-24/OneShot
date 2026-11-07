# OneShot — Development Status

> Last updated: 2026-11-04
> Current phase: **Phase 6 - Cinematic Knowledge / RAG — M6.2 DONE (awaiting review)**
> Next: **M6.3 - retrieval layer**

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
| 5 | Shot Editing and Validation | DONE | PATCH/DELETE/reorder/approve, draft renumbering, continuity rebuild, 22 new tests |
| 6 | Cinematic Knowledge / RAG | IN PROGRESS | M6.2 done: 101-chunk corpus, Qdrant local store, idempotent ingest, auto-seed; retrieval next |
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
- Projects CRUD: create, list, get, delete (hard delete cascades screenplays/scenes/shots/constraints + uploaded files)

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

### Phase 5 — Shot Editing and Validation (DONE)

Implemented:
- `PATCH /shots/{shot_id}` — partial edits via `ShotUpdate`; `status` intentionally
  ignored (approval has its own endpoint); structural errors → 400, constraint
  violations → 409, no partially-applied updates (session rollback)
- `DELETE /shots/{shot_id}` — drafts only; approved shots return 409; remaining
  drafts renumbered contiguously after the highest approved number
- `PUT /shots/{shot_id}/reorder` — path shot identifies the scene; body must be a
  permutation of that scene's drafts; foreign-scene shots → 400, unknown → 404,
  approved shots cannot be reordered (400); approved numbers preserved
- `POST /shots/{shot_id}/approve` — reuses `validate_shot` (structural + constraint
  rules); already approved → 409
- Continuity: stale `[auto]` notes stripped and rebuilt after delete/reorder;
  `ref` values stay consistent because they are derived in `to_schema`
- New domain error `InvalidDataError` mapped to 400 in `api/errors.py`
- Tests: 22 new tests in `tests/test_api_shots.py`, incl. invalid update (400),
  constraint conflict (409), approved protection, reorder/continuity, and the
  generate → edit → delete → reorder → approve → retrieve workflow

### Phase 6 — Cinematic Knowledge / RAG (IN PROGRESS)

M6.1 — LiteRT standardization + embedding foundation (DONE, awaiting review):

- `ai/llm.py`, `config.py`, `/providers`, and route query params are LiteRT-only.
  Gemini/Ollama/Hugging Face/Nomic settings and implementations removed;
  `.env.example` updated. Only Gemma 4 E2B (`:8101`) + EmbeddingGemma 300M
  (`:8100`) remain.
- Embeddings pinned: signature `litert/embeddinggemma-300m`, dimension 768.
  `rag/embeddings.py` validates payloads, L2-normalizes, batches in order with
  bounded concurrency, and raises `EmbeddingModelError` (explicit re-ingestion
  required) on any identity/dimension mismatch.
- Verified live against the local services: 768-dim unit-norm vectors, first
  embedding call 7.2s, 2-item batch 13.7s, LLM reply 4.0s.
- Tests: **169 passed**, 2 pre-existing deprecation warnings, ruff clean
  (new `tests/test_rag_embeddings.py`; provider tests pruned/updated).
- Known constraint: local embedding latency (~7s/call) dominates corpus
  ingestion and adds latency per retrieval query; tracked for M6.2/M6.5.

M6.2 — Knowledge schema, seed corpus, Qdrant store, ingest (DONE, awaiting review):

- `rag/knowledge.py`: `KnowledgeCategory` enum + `KnowledgeChunk`
  (`category`, `title`, `body`, `tags`, `attributes`) with derived
  `chunk_id = "{category}:{slug(title)}"`; loads/validates every JSON file in
  `rag/seed/`, rejects duplicate ids, and hashes the canonical corpus
  (`corpus_sha`).
- Seed corpus (101 chunks, `corpus_sha=b3e44066…`): shot_type 22,
  composition 20, camera_technique 18, lens 15, movement 14, continuity 12.
  Written as practical rules (when to use, what goes wrong), not filler.
- `rag/store.py`: replaceable `QdrantStore` wrapper over `qdrant-client`
  (local-file default under `data/qdrant`, HTTP optional). Point ids are
  `uuid5(namespace, chunk_id)` so re-ingestion is an idempotent upsert.
  Dimension/signature mismatches raise `CollectionMismatchError`; a locked
  local folder raises `VectorStoreError` with an actionable message.
- `rag/ingest.py`: embeds via M6.1 `rag/embeddings.py`, validates count and
  dimensions **before** any destructive step, skips when every stored payload
  matches the current signature + corpus sha, refuses signature drift unless
  `--force`, and exposes `seed_knowledge_if_needed()` + a
  `python -m oneshot.rag.ingest` CLI.
- `main.py` seeds an empty collection in a background lifespan task; failures
  log a warning and never block startup.
- 27 new tests (`test_rag_knowledge.py`, `test_rag_store.py`,
  `test_rag_ingest.py`) covering schema/checksum determinism, local persistence
  and folder locking, idempotent skips, signature drift, dimension mismatch,
  force-rebuild safety, and lifespan auto-seed. Suite **196 passed**, ruff clean.
- Windows qdrant-local quirk: `delete_collection()` leaves the collection's
  SQLite handle open, so a same-name recreate silently reuses old vectors
  (`ValueError: could not broadcast input array ...`). Workaround:
  `gc.collect()` then remove `<storage>/collection/<name>` before recreating.
- Known constraint: local embedding latency (~7s/call) makes a full corpus
  ingest take ~12 minutes; `RAG_EMBED_CONCURRENCY` cannot speed it up because
  the LiteRT service serializes requests.

M6.3–M6.5: see `docs/plan.md` Phase 6 milestones (retrieval, strict pipeline
integration, evaluation).

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
| 2026-09-25 | 1 | api | No way to delete a project | Added `DELETE /projects/{project_id}` — hard delete with explicit child-first cascade in new `services/project_service.py` (constraints → shots → scenes → screenplays → project using table FKs directly, since SQLite FK enforcement is off) + best-effort removal of uploaded source files (guarded to UPLOAD_DIR). Projects list now has a per-row ✕ Delete button (browser `confirm()`, activity-console task log, full workspace reset when the selected project is deleted). Suite 126 passed, ruff clean. |
| 2026-09-25 | 4 | ai | Shots tab returned `502 LLM provider unreachable` after ~180.2s when generating | Root cause: LiteRT on-device decodes ~10 tok/s; a shot list needs 2.5-4k output tokens → 4-10 min, but `httpx.Timeout(180.0)` was hard-coded (ai/llm.py). Fixed: `LLM_TIMEOUT_SECONDS` (default 600, config.py), shot generation capped at `SHOT_MAX_TOKENS` (3072), and `TimeoutException` now maps to **504** ("raise LLM_TIMEOUT_SECONDS or use a faster provider") instead of the misleading 502 (kept for true connection errors). Suite 129 passed. |
| 2026-09-25 | 4 | ai | Live shot generation failed `Shot 1 failed validation: shot_type Field required` even after timeout fix | The model reliably emits `"type"` instead of `"shot_type"` (all other keys match). Added a minimal key-aliasing pass before `AIShotData.model_validate` (type→shot_type only); value validation stays strict (genuine enum/value errors still fail). Verified live end-to-end on dev DB scene 5: analyze 17.9s → generate 93.6s → 4 shots persisted with `[]` warnings. Suite 131 passed, ruff clean. |
| 2026-09-25 | 4 | feature | User: human-friendly shot grammar; establishing shot when location changes (incl. first scene); emotional Close-Up; Extreme Close-Up for character intro/tension; constraints next to shots; ask constraints before generation with Skip | **Prompt** (`prompts.py`): plain-English language-style block + cinematography rules (establishing / emotional Close-Up / ECU intro ≤2 per scene) driven by a `context` object. **Service** (`shot_service.build_scene_context`): injects `first_scene`, `location_changed` (normalized `Scene.location` vs previous scene), `new_characters` as JSON into `{scene_json}`; covers single + batch (batch loops this path). **UI**: native `<dialog id="constraints-dialog">` shown before Generate (per-scene + batch) with **Save & generate / Skip / Cancel**; prefilled from effective-constraint GETs with per-field Override state = applied iff differs from project defaults; Save persists scene overrides (per-scene) or project defaults (batch). Inline `<details class="scene-inline-constraints">` panel per scene card in Shots tab. **Robustness**: `{"type":"array","items":[...]}` envelope unwrapped before validation. Live-verified via Ollama (LiteRT services were down): first shot `Wide` establishing ✓, plain-English action ✓, emotional `Close-Up` ✓, 4 shots persisted, `[]` warnings (ECU-intro rule present but model-dependent — skipped in that particular run). Suite 140 passed, ruff clean. |
| 2026-09-25 | 4 | ai | Shot 1 failed validation with `7 validation errors for AIShotData`, `shot_type` input `'array'` — LiteRT/Gemma 4 E2B echoed the JSON Schema instead of shots | LiteRT's `response_format=json_object` is ignored by `litert-llm-service` (no schema-constrained decoding), so the model occasionally returns the schema inside the array. The unconditional `type→shot_type` alias then rewrote `{"type":"array","items":…}` into `{"shot_type":"array",…}`, masking the real problem as enum/missing-field errors. Fixed in `ai/shot_generator.py`: explicit schema-echo detection (`_is_schema_echo`, keys ⊆ JSON-Schema keys + `items`/`properties`) fails fast with a descriptive error; alias now applies only when the `type` value is a legitimate `ShotType`; raw LLM response logged at DEBUG only on validation failure. `prompts.py`: explicit "never echo the schema" instruction. Tests: +3 (echo rejection, mixed echo+valid → whole response fails, `type` alias still works). Suite 143 passed, ruff clean. |
| 2026-11-03 | 6 | ai/config | Multiple provider paths (Ollama/Gemini/HF/Nomic) contradicted the single-runtime decision; embedding client existed but nothing consumed it | User decision: **LiteRT-only** inference. Removed all alternate provider implementations/settings/endpoints; pinned `litert/embeddinggemma-300m` at **768 dims** with reject-and-re-ingest semantics; added validated, L2-normalized batched embeddings (`rag/embeddings.py`). Suite **169 passed**, ruff clean. M6.2 (Qdrant, corpus, ingest) pending review. |
| 2026-11-04 | 6 | rag/store | qdrant-client 1.20 local mode: deleting and recreating a collection on Windows silently reuses the old vectors (`could not broadcast input array from shape (768,) into shape (8,)`), corrupting the collection | Reproduced in isolation. Root cause: `delete_collection()` does not release the collection's SQLite handle, so the folder cannot be removed and a same-name recreate picks up stale data. Fix in `_recreate_collection`: `gc.collect()` then `shutil.rmtree(<storage>/collection/<name>)` before `create_collection`; verified with a close/delete/reopen/upsert script. |
| 2026-11-04 | 6 | rag | Corpus ingestion must never destroy the current collection on a failed embedding call | Reordered `ingest_corpus`: `--force` (and dimension-mismatch rebuilds) defer the destructive recreate until after every vector is embedded and dimension-checked. Regression test `test_force_rebuild_preserves_data_until_vectors_validate`. |

---

## Blockers

| Blocker | Blocks | Notes |
|---------|--------|-------|
| Qdrant local folder is single-process | Phase 6 (M6.2+) | Local-file mode holds an exclusive lock on `data/qdrant`; a second process gets a clear `VectorStoreError`. Use HTTP mode for concurrent processes. |
| LiteRT LLM service (`:8101`) not running | M6.3/M6.5 | Needed only once retrieval is wired into shot generation; M6.2 ingestion uses the embedding service (`:8100`) only. |

---

## Verification

- Environment: `uv` — symlink `.venv` via `uv sync` (deps from `pyproject.toml`); activate with `uv run`
- Test command: `uv run pytest`
- Lint command: `uv run ruff check src tests`
- Latest run: **196 passed**, 2 warnings (deprecation), ruff clean (2026-11-04)
- Provider: **LiteRT only** — Gemma 4 E2B (`gemma-4-E2B-it`) via `litert_llm_service` on `:8101`, EmbeddingGemma 300M (`embeddinggemma-300m`, 768-dim, pinned) via `embeddinggemma-service` on `:8100`. No alternative providers.
- M6.1 live check (2026-11-03): `rag.embed_text` returned 768-dim unit-norm vectors (7.2s first call, 13.7s for a 2-item batch); `llm.generate` replied in 4.0s.
- M6.2 live ingest (2026-11-04), local Qdrant file store: first run `chunks=101 embedded=101 upserted=101 skipped=0`; second run in a **separate process** `embedded=0 upserted=0 skipped=101`; final collection `oneshot_knowledge` holds 101 points at 768 dims, every payload carries `embedding_signature=litert/embeddinggemma-300m` and `corpus_sha=b3e44066…`; `data/qdrant` is 0.81 MB (3 files).
- Verified end-to-end with live LiteRT services (2026-09-21): `/providers/ping` (LLM + embeddings), project → screenplay upload → full pipeline → 4/4 scenes analyzed → screenplay metadata extracted.