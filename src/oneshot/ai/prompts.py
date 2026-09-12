"""Prompt templates for scene analysis and shot generation."""

SCENE_ANALYSIS_PROMPT = """You are a professional screenwriting analyst.

Given the following screenplay text, extract:
- Scene heading
- Location
- Time of day
- Characters present
- Actions (what happens)
- Dialogue (what is said)
- Narrative context (mood, tone, subtext)

Return as valid JSON with these fields:
{
  "heading": "...",
  "location": "...",
  "time_of_day": "...",
  "characters": [...],
  "actions": [...],
  "dialogue": [...],
  "narrative_context": "..."
}

Screenplay text:
{text}
"""


SHOT_GENERATION_PROMPT = """You are a professional cinematographer and shot planner.

Given the following scene, generate a shot list that tells the story visually.

Scene:
{scene_json}

Production constraints:
{constraints_json}

Generate a list of shots. Each shot must include:
- shot_type (e.g. Wide, Medium, Close-Up)
- camera_angle (e.g. Eye Level, High Angle)
- lens (e.g. 50mm, 85mm)
- camera_movement (e.g. Static, Pan, Dolly)
- duration (seconds)
- characters
- dialogue (if any)
- action
- visual_description
- continuity_notes

Return as valid JSON array of shots.
"""
