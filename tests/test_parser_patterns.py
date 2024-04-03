import pytest

from stagescript.parser import Pattern


@pytest.mark.parametrize(
    ("string", "function_name"), [("/title", "title"), ("/introduce tom; Tom; Tom, just Tom", "introduce")]
)
def test_pattern_function_name(string: str, function_name: str) -> None:
    assert (match := Pattern.function.pattern.match(string)) is not None
    assert match.group("function") == function_name


@pytest.mark.parametrize(
    ("string", "arguments"),
    [
        ("/title", []),
        ("/introduce tom; Tom; Tom, just Tom", ["tom", "Tom", "Tom, just Tom"]),
        ("/test test;without space", ["test", "without space"]),
    ],
)
def test_pattern_function_arguments(string: str, arguments: list[str]) -> None:
    assert list(Pattern.function_arguments.pattern.findall(string)) == arguments


@pytest.mark.parametrize(
    ("pattern", "string", "name"),
    [
        ("script_name", "# Hamlet", "Hamlet"),
        ("script_name", "# Hamlet, the prince of Denmark", "Hamlet, the prince of Denmark"),
        ("script_name", "#Without space", "Without space"),
        ("act_name", "## Act 2", "Act 2"),
        ("act_name", "##Act", "Act"),
        ("scene_name", "### Scene name", "Scene name"),
        ("scene_name", "###Scene name", "Scene name"),
    ],
)
def test_pattern_script_names(pattern: str, string: str, name: str) -> None:
    assert (match := Pattern.by_name(pattern).pattern.match(string)) is not None
    assert match.group("name") == name


@pytest.mark.parametrize(
    ("string", "key", "value"),
    [
        ("key: value", "key", "value"),
        ("another-key: a rather complicated value", "another-key", "a rather complicated value"),
        ("without-space:now it's without a space", "without-space", "now it's without a space"),
    ],
)
def test_pattern_metadata(string: str, key: str, value: str) -> None:
    assert (match := Pattern.metadata.pattern.match(string)) is not None
    assert match.group("key") == key
    assert match.group("value") == value


@pytest.mark.parametrize(
    ("string", "is_comment"),
    [("% is comment", True), ("is not comment", False), (" % looks like a comment, but it's not", False)],
)
def test_pattern_comment(string: str, is_comment: bool) -> None:
    assert bool(Pattern.comment.pattern.match(string)) == is_comment


@pytest.mark.parametrize(
    ("string", "characters"),
    [("@tom:", "@tom"), ("@marc,@tom,@anna:", "@marc,@tom,@anna"), ("@marc, @tom, @anna:", "@marc, @tom, @anna")],
)
def test_pattern_dialogue_extract_characters(string: str, characters: str) -> None:
    assert (match := Pattern.dialogue_start.pattern.match(string)) is not None
    assert match.group("characters") == characters


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
    assert bool(Pattern.dialogue_end.pattern.match(string)) == ends


@pytest.mark.parametrize(
    ("string", "ends"),
    [
        ("plain text does not end the stage direction", False),
        ("> stage direction does not end a stage direction", False),
        ("@tom: a dialogue ends a previous stage direction", True),
        ("% a comment ends a stage direction", True),
        ("\n", False),  # An empty line does not end a stage direction
        ("# Naming ends a stage direction", True),
        ("/introduce a function call ends a direction", True),
    ],
)
def test_pattern_find_stage_direction_end(string: str, ends: bool) -> None:
    assert bool(Pattern.stage_direction_end.pattern.match(string)) == ends


@pytest.mark.parametrize(
    ("string", "mentions"),
    [
        ("@tom and @mike", ("@tom", "@mike")),
        ("@tom", ("@tom",)),
        (
            "@tom walks up to @mike, @mike seems a little bit discouraged by @carl, "
            "but that seems to bother neither @tom nor @mike",
            ("@tom", "@mike", "@mike", "@carl", "@tom", "@mike"),
        ),
    ],
)
def test_pattern_find_mentions_in_text(string: str, mentions: tuple[str, ...]) -> None:
    assert Pattern.mention.pattern.findall(string) == list(mentions)


@pytest.mark.parametrize(
    ("string", "is_direction"),
    [("> this is", True), ("this is not", False), (">neither is this", False), (" > nor this", False)],
)
def test_pattern_find_stage_direction_start(string: str, is_direction: bool) -> None:
    assert bool(Pattern.stage_direction_start.pattern.match(string)) == is_direction


@pytest.mark.parametrize(
    ("name", "pattern"),
    [("function", Pattern.function), ("foo", AttributeError), ("stage_direction_end", Pattern.stage_direction_end)],
)
def test_pattern_find_pattern_by_name(name: str, pattern: Pattern | type[AttributeError]) -> None:
    if type(pattern) is type:
        with pytest.raises(AttributeError, match="No Pattern named"):
            Pattern.by_name(name)
        return
    assert Pattern.by_name(name) is pattern
