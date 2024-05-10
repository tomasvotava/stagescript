from pathlib import Path

import pytest

from stagescript import NodeKind, ParsingError, StageScript, Tokenizer


def test_play_name(parsed_basic: StageScript) -> None:
    assert parsed_basic.name == "test play"


def test_characters_introduced(parsed_basic: StageScript) -> None:
    assert len(parsed_basic.characters) == 2
    assert set(parsed_basic.characters.keys()) == {"foo", "bar"}
    assert parsed_basic.characters["foo"].handle == "foo"
    assert parsed_basic.characters["foo"].name == "Foo"
    assert parsed_basic.characters["foo"].introduce == "Foo, the Fooer"
    assert parsed_basic.characters["bar"].handle == "bar"
    assert parsed_basic.characters["bar"].name == "Bar"
    assert parsed_basic.characters["bar"].introduce == "Bar, the Barer"


def test_basic_flow(parsed_basic: StageScript) -> None:
    assert len(parsed_basic.nodes) == 3
    node_dir = parsed_basic.nodes[0]
    node_speaker = parsed_basic.nodes[1]
    node_dialogue = parsed_basic.nodes[2]
    assert node_dir.kind == NodeKind.STAGE_DIRECTION
    assert len(parsed_basic.nodes[0].children) == 2
    assert node_dir.children[0].kind == NodeKind.MENTION
    assert node_dir.children[0].text == "foo"
    assert node_dir.children[1].kind == NodeKind.TEXT
    assert node_dir.children[1].text == " enters"
    assert node_dir.context.lineno == 5
    assert node_speaker.kind == NodeKind.SPEAKER
    assert node_speaker.text is None
    assert node_speaker.children[0].text == "foo"
    assert node_dialogue.kind == NodeKind.DIALOGUE
    assert node_dialogue.children[0].text == "Hi Bar\n"


def test_included_data(parsed_include: StageScript) -> None:
    assert parsed_include.name == "test play"
    from stagescript.export.json import JSONExporter

    JSONExporter(parsed_include).export("./output")
    acts = list(filter(lambda node: node.kind == NodeKind.ACT, parsed_include.nodes))
    scenes = list(filter(lambda node: node.kind == NodeKind.SCENE, parsed_include.flatten()))
    assert len(acts) == 2
    assert acts[0].children[0].text == "act"
    assert acts[1].children[0].text == "another act"
    assert len(scenes) == 2
    assert scenes[0].children[0].text == "scene"
    assert scenes[1].children[0].text == "another scene"
    assert len(parsed_include.characters) == 1
    assert parsed_include.characters["test"].handle == "test"
    assert parsed_include.characters["test"].name == "Test"
    assert parsed_include.characters["test"].introduce == "Test Testovich"
    assert parsed_include.metadata["key"].value == "value"


def test_unknown_function(script_unknown_function: Path) -> None:
    with pytest.raises(ParsingError, match=".*Called to undefined function .nonexistent."):
        Tokenizer.parse(script_unknown_function)


def test_recursive_include(script_circular_include: Path) -> None:
    with pytest.raises(ParsingError, match="Cannot process file .* - circular include"):
        Tokenizer.parse(script_circular_include)


def test_recursive_include_passes_dry_run(script_circular_include: Path) -> None:
    script = Tokenizer.parse(script_circular_include, dry_run=True)
    violation = filter(lambda v: "circular include" in v.description, script.violations)
    assert list(violation)


def test_include_nonexistent(script_include: Path) -> None:
    (script_include.parent / "included.play").unlink()
    with pytest.raises(ParsingError, match="Included path .* is not an existing file"):
        Tokenizer.parse(script_include)


def test_include_nonexistent_passes_dry_run(script_include: Path) -> None:
    (script_include.parent / "included.play").unlink()
    script = Tokenizer.parse(script_include, dry_run=True)
    violation = filter(lambda v: "is not an existing file" in v.description, script.violations)
    assert list(violation)


def test_identify_declension(parsed_declension: StageScript) -> None:
    assert len(parsed_declension.nodes) == 1
    node = parsed_declension.nodes[0]
    assert node.kind == NodeKind.STAGE_DIRECTION
    assert len(node.children) == 3
    assert node.children[0].kind == NodeKind.TEXT
    assert node.children[0].text == "Dívá se na "
    assert node.children[1].kind == NodeKind.MENTION_WITH_DECLENSION
    assert node.children[1].children[0].kind == NodeKind.MENTION
    assert node.children[1].children[0].text == "gertrude"
    assert node.children[1].children[1].kind == NodeKind.DECLENSION
    assert node.children[1].children[1].text == "Gertrudu"
    assert node.children[2].kind == NodeKind.TEXT
    assert node.children[2].text == " naštvaně"
