"""Screenplay scene detection.

Two-layer approach:
1. Regex layer recognises screenplay scene headings (INT./EXT./I.E.).
2. A line-by-line rule engine classifies screenplay elements and builds
   raw-text blocks between headings.
"""

import re
from dataclasses import dataclass
from enum import Enum


class LineKind(str, Enum):
    BLANK = "blank"
    HEADING = "heading"
    ACTION = "action"
    CHARACTER = "character"
    PARENTHETICAL = "parenthetical"
    DIALOGUE = "dialogue"


_SCENE_HEADING_RE = re.compile(
    r"^(INT\.?|EXT\.?|INT\.?/EXT\.?|I\.?/E\.?|INT\.?-EXT\.?)\s+(.+)$",
    re.IGNORECASE,
)

_TIME_TOKEN_RE = re.compile(r"[-–—]\s*([A-Za-z0-9].{0,40})$")

_ALL_CAPS_RE = re.compile(r"^[A-Z0-9'.\-&]{2,}\s*$")


@dataclass
class SceneBlock:
    scene_number: int
    heading: str
    location: str
    time_of_day: str | None
    raw_text: str
    line_start: int
    line_end: int


@dataclass
class ClassifiedLine:
    kind: LineKind
    text: str
    line_number: int


def parse_heading(line: str) -> dict | None:
    """Parse a scene heading into location and optional time of day."""
    stripped = line.strip()
    match = _SCENE_HEADING_RE.match(stripped)
    if not match:
        return None

    rest = match.group(2).strip()
    time_match = _TIME_TOKEN_RE.search(rest)
    if time_match:
        location = rest[: time_match.start()].strip()
        time_of_day = time_match.group(1).strip()
    else:
        location = rest
        time_of_day = None

    return {
        "heading": stripped,
        "location": location or stripped,
        "time_of_day": time_of_day,
    }


def classify_line(line: str, line_number: int, prev_kind: LineKind) -> ClassifiedLine:
    """Classify a single line of screenplay text using screenplay conventions."""
    text = line.strip()

    if not text:
        return ClassifiedLine(LineKind.BLANK, "", line_number)

    if parse_heading(text) is not None:
        return ClassifiedLine(LineKind.HEADING, text, line_number)

    if text.startswith("(") and text.endswith(")") and len(text) < 60:
        return ClassifiedLine(LineKind.PARENTHETICAL, text, line_number)

    words = text.split()
    if (
        _ALL_CAPS_RE.match(text)
        and len(text) <= 40
        and 1 <= len(words) <= 4
    ):
        return ClassifiedLine(LineKind.CHARACTER, text, line_number)

    if prev_kind in (LineKind.CHARACTER, LineKind.PARENTHETICAL, LineKind.DIALOGUE):
        return ClassifiedLine(LineKind.DIALOGUE, text, line_number)

    return ClassifiedLine(LineKind.ACTION, text, line_number)


def detect_scenes(text: str) -> list[SceneBlock]:
    """Parse screenplay text into scene blocks by detecting scene headings."""
    lines = text.splitlines()

    blocks: list[SceneBlock] = []
    current: SceneBlock | None = None
    prev_kind = LineKind.BLANK
    scene_number = 0

    for idx, line in enumerate(lines, start=1):
        classified = classify_line(line, idx, prev_kind)

        if classified.kind == LineKind.HEADING:
            if current is not None:
                blocks.append(current)
            scene_number += 1
            parsed = parse_heading(classified.text) or {
                "heading": classified.text,
                "location": classified.text,
                "time_of_day": None,
            }
            current = SceneBlock(
                scene_number=scene_number,
                heading=parsed["heading"],
                location=parsed["location"],
                time_of_day=parsed["time_of_day"],
                raw_text="",
                line_start=idx,
                line_end=idx,
            )
        elif current is not None:
            if classified.kind != LineKind.BLANK:
                current.raw_text += classified.text + "\n"
            current.line_end = idx

        if classified.kind != LineKind.BLANK:
            prev_kind = classified.kind

    if current is not None:
        blocks.append(current)

    for block in blocks:
        block.raw_text = block.raw_text.strip()

    return blocks