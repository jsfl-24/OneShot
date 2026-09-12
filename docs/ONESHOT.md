# OneShot: AI Shot Segmentation and Storyboard Generation

## 1. Project Brief

Build an AI-assisted filmmaking pre-production system that:

1. Accepts a screenplay in PDF, DOCX, or plain-text format.
2. Extracts and parses the screenplay.
3. Detects scenes and understands their characters, actions, dialogue, and narrative context.
4. Converts each scene into a meaningful, cinematic shot plan.
5. Applies real production constraints supplied by the filmmaker.
6. Allows the filmmaker to review and edit the generated shot plan.
7. Validates the edited shot plan.
8. Optionally generates storyboard prompts and storyboard images.
9. Exports the approved production plan.

The primary research contribution is **AI-based shot segmentation and cinematic shot planning**. Storyboard generation is a secondary feature.

This application should be usable as a local/edge AI tool so filmmakers can protect private movie ideas and scripts. Do not assume that screenplay data should be sent to third-party hosted AI services.

## 2. Product Workflow

```text
Screenplay (PDF/DOCX/Text)
        |
        v
Document extraction
        |
        v
Screenplay and scene parsing
        |
        v
Character, action, dialogue, and narrative understanding
        |
        v
Filmmaker production constraints
        |
        v
AI shot segmentation
        |
        v
Initial shot list
        |
        v
Filmmaker review and editing
        |
        v
Shot validation
        |
        v
Approved shot list
        |
        v
Storyboard prompt generation
        |
        v
Optional storyboard generation
        |
        v
Production plan export
```

## 3. Scope and Priorities

Implement the system in this priority order:

1. Correct screenplay understanding.
2. Reliable scene extraction.
3. High-quality shot segmentation.
4. Cinematic reasoning.
5. Production-constraint handling.
6. Easy shot-list review and editing.
7. Shot validation.
8. Storyboard prompt generation and image generation.
9. Export.
10. Frontend polish.

Start backend-first. Do not build the complete frontend before the backend APIs and data flow are stable.

## 4. Proposed Technology Stack

Use these technologies unless a documented technical reason requires a change:

- **Language:** Python
- **API framework:** FastAPI
- **Validation and schemas:** Pydantic
- **Intermediate representation:** JSON
- **PDF extraction:** PyMuPDF
- **DOCX extraction:** python-docx
- **Initial database:** SQLite
- **Vector database:** Qdrant
- **Initial local model serving:** Ollama
- **Model:** Gemma 4 E4B from Hugging Face during development, then Gemma 4 E4B served through the user's Ollama server for deployment
- **Fine-tuning, only if needed later:** Hugging Face Transformers, PEFT, and QLoRA
- **Version control:** Git and GitHub

The exact LLM/model integration must remain replaceable until research and testing confirm the final choice.

## 5. Modular Backend Architecture

The backend should be organized into independently testable modules:

1. Document Parser
2. Screenplay Parser
3. Scene Analyzer
4. Constraint Manager
5. Cinematic Knowledge/RAG Layer
6. Shot Segmentation Engine
7. Shot Validation Service
8. Storyboard Prompt Builder
9. Storyboard Generator
10. Export Service
11. Project and Shot Management

Recommended request flow:

```text
FastAPI route
    -> service layer
        -> domain/model layer
        -> persistence layer
        -> isolated AI/LLM layer when needed
```

API routes must remain thin. AI logic must not be placed directly in route files.

## 6. Core Domain Entities

### Project

- `id`
- `name`
- `description`
- `created_at`
- `updated_at`

### Screenplay

The screenplay belongs to a project and should retain both the uploaded document metadata and the extracted text/structured representation.

Recommended fields:

- `id`
- `project_id`
- `filename`
- `format`
- `source_path` or storage reference
- `extracted_text`
- `created_at`

### Scene

- `id`
- `project_id`
- `scene_number`
- `heading`
- `location`
- `time_of_day`
- `characters`
- `actions`
- `dialogue`
- `narrative_context`

### Shot

This is the most important entity and the backbone of the backend:

- `id`
- `scene_id`
- `shot_number`
- `shot_type`
- `camera_angle`
- `lens`
- `camera_movement`
- `duration`
- `characters`
- `dialogue`
- `action`
- `visual_description`
- `continuity_notes`
- `director_notes`
- `status`

Use a structured representation for every generated shot. Example:

```json
{
  "shot_id": "S01_SH03",
  "scene_id": "S01",
  "shot_number": 3,
  "shot_type": "Medium Close-Up",
  "camera_angle": "Eye Level",
  "lens": "50mm",
  "camera_movement": "Static",
  "duration": 4,
  "characters": ["John"],
  "dialogue": "Where were you?",
  "action": "John looks toward Mary.",
  "visual_description": "John confronts Mary with a tense expression.",
  "continuity_notes": "Maintain eyeline with previous shot.",
  "director_notes": "",
  "status": "draft"
}
```

The filmmaker must be able to modify all editable shot fields after AI generation.

### Production Constraints

Keep production constraints separate from shot data. The AI must generate shots that are filmable within the filmmaker's resources, not merely visually interesting.

- `location_constraints`
- `camera_movement_allowed`
- `high_angle_possible`
- `low_angle_possible`
- `available_lenses`
- `equipment_constraints`
- `director_preferences`
- `additional_notes`

### Storyboard

Associate storyboard prompts and generated images with approved shots. Keep this feature optional and independent from the core shot-segmentation pipeline.

## 7. Shot-Planning Reasoning Model

The conceptual transformation is:

```text
Scene
  -> narrative events
  -> character actions
  -> dialogue exchanges
  -> visual and cinematic requirements
  -> shot boundaries
  -> structured shot attributes
```

Shot boundaries should be based on meaningful changes such as:

- A change in subject or character focus.
- A new action or narrative beat.
- A meaningful dialogue exchange.
- A change in visual information required by the story.
- A change in camera position, angle, or coverage required for continuity.

The implementation should use cinematic reasoning rather than splitting text mechanically by sentence.

## 8. Development Phases

Implement and test one phase at a time:

### Phase 1: Backend Foundation

- Establish the project structure.
- Configure FastAPI.
- Define persistence models.
- Define separate Pydantic API schemas.
- Establish configuration and error handling.
- Add a minimal health/status endpoint.

### Phase 2: Document to Scene Extraction

- Implement PDF, DOCX, and text ingestion.
- Extract normalized screenplay text.
- Detect screenplay scene headings.
- Persist projects, screenplays, and scenes.
- Add tests using representative fixtures.

### Phase 3: Structured Scene Understanding

- Extract characters, actions, dialogue, and narrative context.
- Return validated structured JSON/Pydantic output.
- Keep LLM calls behind an isolated interface.

### Phase 4: Scene to Shot Segmentation

- Generate an initial shot list from a structured scene.
- Apply production constraints during generation.
- Validate every generated shot before persistence.
- Preserve traceability from each shot to its scene and source context.

### Phase 5: Shot Editing and Validation

- Add APIs to read, update, reorder, and delete shots.
- Validate required fields, durations, references, and continuity-related data.
- Support draft and approved shot statuses.

### Phase 6: Cinematic Knowledge/RAG

- Cinematic knowledge retrieval is **mandatory** and must be integrated into the shot-generation pipeline.
- Add the cinematic knowledge retrieval layer after the baseline pipeline works, then make it part of shot generation.
- Keep Qdrant and retrieval logic replaceable, but the pipeline is not complete without RAG.
- Do not provide a non-RAG fallback path for shot generation; shot generation always augments with retrieved cinematic context.

### Phase 7: Storyboard Generation

- Build prompts from approved shot data.
- Add optional image generation.
- Keep storyboard failures from corrupting the shot plan.

### Phase 8: Frontend

- Build the frontend only after backend APIs, schemas, and data flow are stable.
- Prioritize screenplay/scene navigation, shot-list editing, validation feedback, and approval workflow.

## 9. Backend Development Rules for the Coding Agent

- Complete the backend before the frontend.
- Use a modular architecture.
- Keep API routes thin; routes must call service-layer functions.
- Do not put AI logic directly inside API route files.
- Keep database models separate from Pydantic request/response schemas.
- Keep LLM interaction isolated behind an interface or service.
- Use structured JSON/Pydantic models for all AI outputs.
- Never depend on free-form LLM text where structured data is required.
- The LLM must not directly modify the database.
- Validate all AI-generated shot data before storing it.
- Keep model serving replaceable; the final model is not yet permanently selected.
- Keep RAG implementation replaceable, but RAG is a required part of the shot-generation pipeline.
- Fine-tuning (QLoRA) is optional; implement it only if the baseline pipeline with RAG is working and has been evaluated.
- Do not implement storyboard generation or frontend work ahead of the core pipeline.
- Make every module independently testable.
- Implement incrementally; do not generate the entire application in one step.
- Preserve screenplay privacy by default and avoid external AI/API dependencies unless explicitly configured.
- Surface errors clearly. Do not silently discard invalid input or failed AI output.
- Add or update focused tests whenever behavior is introduced or changed.

## 10. Initial API Surface

The backend should progressively expose APIs for:

- Project creation and retrieval.
- Screenplay upload and retrieval.
- Screenplay parsing.
- Scene detection and retrieval.
- Scene analysis.
- Production-constraint creation and update.
- Shot-plan generation.
- Shot retrieval, editing, reordering, and deletion.
- Shot validation and approval.
- Storyboard prompt generation.
- Optional storyboard image generation.
- Final production-plan export.

Do not implement every endpoint at once. Add each endpoint alongside its service, schemas, persistence behavior, and tests.

## 11. Definition of Done for the Core MVP

The backend MVP is ready for frontend work when it can:

1. Ingest a screenplay document locally.
2. Extract and persist screenplay text.
3. Detect and persist scenes.
4. Produce structured scene understanding.
5. Generate a constraint-aware shot list.
6. Validate and persist shots safely.
7. Allow shot data to be edited and approved through APIs.
8. Run without requiring a hosted AI provider.
9. Be tested module by module.

When implementing the project, first inspect the existing repository and its conventions. Then make the smallest coherent change for the current phase, run the relevant existing checks, and report what was implemented, what was tested, and what remains.

## 12. Final Development Instruction

I do not want the software to be built completely and automatically in one step. I want step-by-step development with clearly defined implementation steps. Complete and validate each step before moving to the next one.

The final polished UI will be set up at the end. A rough UI may be created earlier only when it is useful for testing or demonstrating the backend APIs and workflow. Do not spend time polishing or fully implementing the final UI until the backend and core data flow are stable.
