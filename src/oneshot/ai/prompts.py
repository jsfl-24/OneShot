"""Prompt templates for scene detection, scene analysis, and shot generation."""

SCENE_DETECTION_PROMPT = """You are a screenplay editor. Identify every scene in the screenplay text below.

A new scene begins when:
- The location changes
- The time of day changes
- There is a time jump
- The characters present change significantly

Some scenes may have typos in their headings (e.g. "INT.", "EXT", "EEXT.", "IN T.COFFEE") or may be missing a heading entirely. Detect them anyway.

Return ONLY valid JSON:
{{
  "scenes": [
    {{"line_number": 1, "heading": "INT. COFFEE SHOP - DAY", "type": "new"}},
    {{"line_number": 15, "heading": "EXT. STREET - NIGHT", "type": "correction", "original": "EXT. STREE - NIGHT"}}
  ]
}}

- line_number: 1-based line where the scene starts in the text
- heading: standardized heading (INT./EXT. LOCATION - TIME OF DAY)
- type: "new" if this scene was missing entirely, "correction" if it fixes a heading that already looks like a scene heading but has typos
- original: the original typo heading, only for corrections

Screenplay text:
{text}
"""


SCENE_ANALYSIS_PROMPT = """You are a professional screenwriting analyst.

Given the following screenplay scene, extract structured data.

Return ONLY valid JSON:
{{
  "characters": ["JANE", "MARK"],
  "actions": ["Jane sips her coffee."],
  "dialogue": ["JANE: I cannot believe you are late again."],
  "narrative_context": "Tense reunion; subdued mood."
}}

Rules:
- characters: ALL-CAPS character names present in the scene
- actions: what happens visually (not dialogue)
- dialogue: lines prefixed with the character name
- narrative_context: 1-2 sentences on mood, tone, and subtext

Scene text:
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


SCREENPLAY_ANALYSIS_PROMPT = """You are a professional screenplay analyst.

Given the full text of a screenplay, extract the following metadata.

Return ONLY valid JSON:
{{
  "one_liner": "A single sentence summarizing the entire film.",
  "genre": "The primary genre (e.g. Thriller, Romance, Sci-Fi, Drama, Comedy, Horror).",
  "story_abstract": "A 2-4 sentence abstract covering the main story arc, central conflict, and resolution.",
  "characters": ["CHARACTER NAME 1", "CHARACTER NAME 2"]
}}

Rules:
- one_liner: one sentence, no more than 30 words.
- genre: a single genre label.
- story_abstract: concise summary of the plot, not a scene-by-scene breakdown.
- characters: ALL major character names in ALL-CAPS, listed in order of importance.

Screenplay text:
{text}
"""
