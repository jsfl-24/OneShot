# AGENTS.md

## Project status

- This is a **pre-build repo**: no application code, no manifests, no Python env yet. Git repo has no commits.
- `oneshot.txt` is the authoritative product spec and the source of truth for all work. Read it before writing code; it defines the tech stack (Python, FastAPI, Pydantic, SQLite, Qdrant, Ollama/Gemma), module layout, and API surface.

## Development rules (from `oneshot.txt`)

- Build backend-first, frontend last. Never generate the entire app in one step; make the smallest coherent change for the current phase, then validate before moving on (spec §9, §12).
- Keep API routes thin (route → service → domain → persistence → isolated AI/LLM layer). No AI logic in route files.
- Keep DB models separate from Pydantic API schemas; LLM must never touch the DB directly and never emit free-form text where structured JSON/Pydantic output is required.
- Validate all AI-generated shot data before persisting.
- Keep LLM serving and RAG layers replaceable; preserve screenplay privacy (no third-party hosted AI by default).
- Add or update focused tests alongside new behavior (per-module tests).

## Skills

- Installed skills: `ai-sdk` (`.agents/skills/ai-sdk/SKILL.md`) and `frontend-design` (`.agents/skills/frontend-design/SKILL.md`). Load them when working on AI SDK integrations or UI. Lockfile: `skills-lock.json`.

## Rules for AI agent

* Always ask clarifying questions
* Never assume design, tech stack or features

## Critical rules

### Responses

- Keep responses concise and to the point unless the user asks otherwise.

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
