# AGENTS.md

## Project status

- Phases 1–5 (backend foundation, document/scene extraction, structured scene
  analysis, shot segmentation, shot editing and validation) are **implemented,
  verified and committed**: FastAPI + SQLite/SQLModel backend under
  `src/oneshot/`, Alembic migrations. See `docs/STATUS.md` for the
  phase-by-phase log.
- Phase 6 — Cinematic Knowledge / RAG (mandatory in the shot pipeline):
  - **M6.1 — done, approved, committed:** LiteRT-only inference; embeddings
    pinned to `litert/embeddinggemma-300m` at **768 dimensions** with
    reject-and-re-ingest semantics (`rag/embeddings.py`).
  - **M6.2 — done, approved, committed:** 101-chunk curated corpus in
    `rag/seed/`, validated schema (`rag/knowledge.py`), Qdrant store and
    idempotent ingestion (`rag/store.py`, `rag/ingest.py`), startup auto-seed.
  - **M6.3 — Retrieval layer is next.** M6.4 (strict pipeline integration) and
    M6.5 (evaluation and tuning) remain pending.
- **LiteRT-only architecture** (no third-party hosted AI):
  - LLM: Gemma 4 E2B via `litert_llm_service` on `:8101`.
  - Embeddings: EmbeddingGemma 300M via `embeddinggemma-service` on `:8100`,
    768-dimensional, identity pinned.
  - Vector store: **Qdrant via `qdrant-client`** — local-file mode by default
    (`data/qdrant`, one process at a time), optional HTTP mode for deployment.
- `/ui` is a **temporary development/testing harness** only; the production
  frontend is deferred to Phase 8.
- `docs/ONESHOT.md` is the authoritative product spec and the source of truth for all work. Read it before writing code; it defines the tech stack (Python, FastAPI, Pydantic, SQLite, Qdrant, LiteRT/Gemma), module layout, and API surface. `docs/plan.md` is the task checklist tracking progress.
- Python environment is managed with **uv** (not mamba/conda). Create/use the venv via `uv sync` / `uv run`; install packages as `uv add`, run all commands through `uv run`.

## Development rules (from `docs/ONESHOT.md`)

- Build backend-first, frontend last. Never generate the entire app in one step; make the smallest coherent change for the current phase, then validate before moving on (spec §9, §12).
- Keep API routes thin (route → service → domain → persistence → isolated AI/LLM layer). No AI logic in route files.
- Keep DB models separate from Pydantic API schemas; LLM must never touch the DB directly and never emit free-form text where structured JSON/Pydantic output is required.
- Validate all AI-generated shot data before persisting.
- Keep LLM serving and RAG implementation replaceable; RAG is a required part of the shot-generation pipeline. Preserve screenplay privacy (no third-party hosted AI by default).
- Add or update focused tests alongside new behavior (per-module tests).

## Skills

- Installed skills: `ai-sdk` (`.agents/skills/ai-sdk/SKILL.md`) and `frontend-design` (`.agents/skills/frontend-design/SKILL.md`). Load them when working on AI SDK integrations or UI. Lockfile: `skills-lock.json`.

## Rules for AI agent

* Always ask clarifying questions
* Never assume design, tech stack or features

## Critical rules

### Responses

- Keep responses concise and to the point unless the user asks otherwise.
- Avoid unwanted greeding and appreciations dont waste tokens and time on unwanted english

### Planning mode

- Always ask clarifying questions; never assume design, tech stack, or features.
- Use deep-dive sub-agents to research and to review the different aspects of a plan before presenting it.

### Change / edit mode

- Never implement features yourself when a sub-agent can — act as coordinator.
- Identify changes that can be implemented in parallel and run them via sub-agents.
- Use the best model for the task (premium for complex coding, mid-tier for simple docs).
- After completing work (large or small), run lint, typecheck, and build to verify code quality.

### Database schema changes

- Whenever the DB schema changes, always run the migration generate + migrate commands, then apply them.
- Never push schema changes directly to the database (no `drizzle push`-style sync). If the ORM/migration tool differs from drizzle, apply the equivalent generate-and-migrate flow.

### Testing

- Use any testing tools/libraries available in the project to test changes. Never assume changes work — always test.
- If no testing tools, scripts, MCP tools, or skills exist, ask the user whether testing should be skipped.

### UI design

- Always follow the UI design system when creating or reviewing components or pages.
- A `DESIGN.md` design system will be added during Phase 8 (frontend). Until it exists, load the `frontend-design` skill before any UI work.

## Development Workflow

1. Read relevant existing code before making changes.
2. Verify the current implementation instead of assuming documented status is accurate.
3. Prefer minimal, incremental changes over unnecessary refactoring.
4. Reuse existing schemas, services, utilities and conventions.
5. Never modify unrelated functionality.
6. Preserve existing user changes and uncommitted work.
7. Never delete code, files or dependencies without verifying they are genuinely unused.
8. Do not silently change API contracts, database schemas or application behavior.
9. Add regression tests for every bug fix.
10. Run relevant tests and Ruff after implementation.
11. Report actual test results, modified files and unresolved issues.
12. Never claim functionality is verified without evidence.

## Task Execution

* Planning and implementation are separate stages for architectural or multi-module changes.
* For small, isolated fixes, avoid unnecessary planning overhead.
* Request approval before proceeding when a proposed change has significant architectural or data-model implications.
* Do not repeatedly request approval for already-approved task requirements.
* Work only within the explicitly assigned scope.
* Stop after completing the requested milestone.
