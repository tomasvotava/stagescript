import re

import pytest

from stagescript.tokenizer import dialogue_stop_pattern, toplevel_patterns


@pytest.mark.parametrize(
    ("string", "function_name", "function_arguments"),
    [("/title", "title", None), ("/introduce tom; Tom; Tom, just Tom", "introduce", "tom; Tom; Tom, just Tom")],
)
def test_pattern_function(string: str, function_name: str, function_arguments: str | None) -> None:
    assert (match := re.match(toplevel_patterns["function"], string)) is not None
    assert match.group("function") == function_name
    assert match.group("function_arguments") == function_arguments


@pytest.mark.parametrize(
    ("pattern_name", "string", "name"),
    [
        ("play_name", "# Hamlet", "Hamlet"),
        ("play_name", "# Hamlet, the prince of Denmark", "Hamlet, the prince of Denmark"),
        ("play_name", "#Without space", "Without space"),
        ("act_name", "## Act 2", "Act 2"),
        ("act_name", "##Act", "Act"),
        ("scene_name", "### Scene name", "Scene name"),
        ("scene_name", "###Scene name", "Scene name"),
    ],
)
def test_pattern_script_names(pattern_name: str, string: str, name: str) -> None:
    assert (match := re.match(toplevel_patterns[pattern_name], string)) is not None
    assert match.group(pattern_name) == name


@pytest.mark.parametrize(
    ("string", "key", "value"),
    [
        ("key: value", "key", "value"),
        ("another-key: a rather complicated value", "another-key", "a rather complicated value"),
        ("without-space:now it's without a space", "without-space", "now it's without a space"),
    ],
)
def test_pattern_metadata(string: str, key: str, value: str) -> None:
    assert (match := re.match(toplevel_patterns["metadata"], string)) is not None
    assert match.group("key") == key
    assert match.group("value") == value


@pytest.mark.parametrize(
    ("string", "characters"),
    [
        ("@tom: is talking", "@tom"),
        ("@marc,@tom,@anna: are talking", "@marc,@tom,@anna"),
        ("@marc, @tom, @anna: are all talking", "@marc, @tom, @anna"),
    ],
)
def test_pattern_dialogue_extract_characters(string: str, characters: str) -> None:
    assert (match := re.match(toplevel_patterns["dialogue"], string)) is not None
    assert match.group("speaker") == characters


@pytest.mark.parametrize(
    ("string", "ends"),
    [
        ("plain text does not end the dialogue", False),
        ("> stage direction ends dialogue", True),
        ("@tom: a dialogue ends a previous dialogue", True),
        ("% a comment ends a dialogue", True),
        ("\n", False),  # An empty line does not end a dialogue
        ("# Naming ends a dialogue", True),
        ("/introduce a function call ends a dialogue", True),
    ],
)
def test_pattern_find_dialogue_end(string: str, ends: bool) -> None:
    assert bool(re.match(dialogue_stop_pattern, string)) == ends


@pytest.mark.parametrize(
    ("string", "is_direction"),
    [("> this is", True), ("this is not", False), (">neither is this", False), (" > nor this", False)],
)
def test_pattern_find_stage_direction_start(string: str, is_direction: bool) -> None:
    assert bool(re.match(toplevel_patterns["stage_direction"], string)) == is_direction
