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

Transform the given scene into a cinematic shot list. Your shots must tell the
story visually and be filmable within the production constraints.

Use cinematic reasoning, never mechanical text splitting:
- A new shot starts when the subject or character focus changes.
- A new shot starts when a new action beat or narrative event begins.
- A new shot starts when a meaningful dialogue exchange begins or the speaker changes.
- A new shot starts when the story requires different visual information.
- A new shot starts when a camera position, angle, or coverage change is needed for continuity.
- Respect the 180-degree rule, eyelines, shot/reverse-shot coverage, and spatial consistency
  between consecutive shots.

Shot count: scale to the scene. A short beat needs 1-2 shots; a dense scene with several
beats typically needs 3-8 shots. Do not pad for length and do not compress an involved
scene into a single shot.

Production constraints (these are hard limits - do not violate them):
{constraints_json}

Scene to plan:
{scene_json}

Rules for every shot:
- shot_type, camera_angle, and camera_movement MUST use one of the exact enum values
  provided in the schema below. Do not invent values, abbreviations, or free text
  (e.g. use "Medium Close-Up", never "MCU").
- lens: a real focal length such as "50mm" or "85mm"; it MUST be in the constraint's
  available lenses list when constraints are provided.
- duration: a realistic duration in whole seconds (2-12), scaled to action complexity.
  Durations are always editable later by the filmmaker.
- characters: ALL-CAPS names actually present in the scene's character list.
- action: the concrete on-screen action of the shot.
- visual_description: what the frame should look like at a glance.
- continuity_notes: describe continuity relative to the neighboring shots WITHOUT
  referencing absolute shot numbers (the numbers are assigned later), e.g.
  "maintain eyeline with previous shot", "screen direction stays consistent".
- director_notes: optional flourish or staging intent; empty string when not needed.

Return ONLY a valid JSON array of shot objects. Every object must conform exactly to
this schema (all required keys present):

{schema_json}
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
