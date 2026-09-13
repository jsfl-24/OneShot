"""Tests for the screenplay scene detector."""

from oneshot.parsers.scene_detector import (
    LineKind,
    classify_line,
    detect_scenes,
    parse_heading,
)


def test_parse_heading_with_time_of_day():
    parsed = parse_heading("INT. COFFEE SHOP - DAY")
    assert parsed == {
        "heading": "INT. COFFEE SHOP - DAY",
        "location": "COFFEE SHOP",
        "time_of_day": "DAY",
    }


def test_parse_heading_without_time_of_day():
    parsed = parse_heading("EXT. STREET")
    assert parsed["location"] == "STREET"
    assert parsed["time_of_day"] is None


def test_parse_heading_ie_slash():
    parsed = parse_heading("INT./EXT. CAR - NIGHT")
    assert parsed["location"] == "CAR"
    assert parsed["time_of_day"] == "NIGHT"


def test_parse_heading_rejects_action_line():
    assert parse_heading("The rain falls hard.") is None


def test_classify_rejects_short_location():
    classified = classify_line("INT. A", 1, LineKind.BLANK)
    assert classified.kind != LineKind.HEADING


def test_classify_character_name():
    classified = classify_line("JANE", 5, LineKind.ACTION)
    assert classified.kind == LineKind.CHARACTER


def test_classify_dialogue_after_character():
    classified = classify_line("Where were you?", 6, LineKind.CHARACTER)
    assert classified.kind == LineKind.DIALOGUE


def test_classify_parenthetical():
    parenthetical = classify_line("(grinning)", 7, LineKind.CHARACTER)
    assert parenthetical.kind == LineKind.PARENTHETICAL


def test_classify_action_after_heading():
    classified = classify_line("Rain falls hard.", 6, LineKind.HEADING)
    assert classified.kind == LineKind.ACTION


def test_detect_scenes_from_sample(sample_screenplay_path):
    text = sample_screenplay_path.read_text(encoding="utf-8")
    blocks = detect_scenes(text)

    assert len(blocks) == 4

    assert blocks[0].scene_number == 1
    assert blocks[0].heading == "INT. COFFEE SHOP - DAY"
    assert blocks[0].location == "COFFEE SHOP"
    assert blocks[0].time_of_day == "DAY"

    assert blocks[1].heading == "EXT. STREET - NIGHT"
    assert blocks[1].location == "STREET"

    assert blocks[2].heading == "INT. CAR - CONTINUOUS"
    assert blocks[2].time_of_day == "CONTINUOUS"

    assert blocks[3].heading == "EXT. ROOFTOP - DAWN"
    assert blocks[3].time_of_day == "DAWN"


def test_scene_raw_text_contains_dialogue(sample_screenplay_path):
    text = sample_screenplay_path.read_text(encoding="utf-8")
    blocks = detect_scenes(text)
    assert "I cannot believe you are late again." in blocks[0].raw_text


def test_detect_scenes_from_second_sample():
    text = (
        "FADE IN:\n\n"
        "INT. OFFICE - DAY\n\n"
        "Papers everywhere.\n\n"
        "INT. CONFERENCE ROOM - LATER\n\n"
        "A long table.\n"
    )
    blocks = detect_scenes(text)
    assert len(blocks) == 2
    assert blocks[0].location == "OFFICE"
    assert blocks[1].location == "CONFERENCE ROOM"


def test_scene_numbering_increments(sample_screenplay_path):
    text = sample_screenplay_path.read_text(encoding="utf-8")
    blocks = detect_scenes(text)
    assert [b.scene_number for b in blocks] == [1, 2, 3, 4]


def test_rejects_false_heading_without_dash():
    text = (
        "INT. COFFEE SHOP - DAY\n\n"
        "The barista makes a latte.\n\n"
        "INT. A\n\n"
        "This should not be a new scene.\n"
    )
    blocks = detect_scenes(text)
    assert len(blocks) == 1
    assert blocks[0].heading == "INT. COFFEE SHOP - DAY"