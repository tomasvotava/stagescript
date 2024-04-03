from pathlib import Path

import pytest

from stagescript.entities import DocumentFlowItemKind
from stagescript.parser import ParsingError, StagescriptParser


def test_play_name(parsed_basic: StagescriptParser) -> None:
    assert parsed_basic.name == "test play"


def test_characters_introduced(parsed_basic: StagescriptParser) -> None:
    assert len(parsed_basic.characters) == 2
    assert set(parsed_basic.characters.keys()) == {"foo", "bar"}
    assert parsed_basic.characters["foo"].handle == "foo"
    assert parsed_basic.characters["foo"].name == "Foo"
    assert parsed_basic.characters["foo"].introduce == "Foo, the Fooer"
    assert parsed_basic.characters["bar"].handle == "bar"
    assert parsed_basic.characters["bar"].name == "Bar"
    assert parsed_basic.characters["bar"].introduce == "Bar, the Barer"


def test_basic_flow(parsed_basic: StagescriptParser) -> None:
    assert len(parsed_basic.flow) == 4
    assert parsed_basic.flow[0].kind == DocumentFlowItemKind.MENTION
    assert parsed_basic.flow[0].content == "foo"
    assert parsed_basic.flow[0].context.lineno == 5
    assert parsed_basic.flow[1].kind == DocumentFlowItemKind.STAGE_DIRECTION
    assert parsed_basic.flow[1].content == "enters"
    assert parsed_basic.flow[1].context.lineno == 5
    assert parsed_basic.flow[2].kind == DocumentFlowItemKind.SPEAKER
    assert parsed_basic.flow[2].content == "foo"
    assert parsed_basic.flow[2].context.lineno == 6
    assert parsed_basic.flow[3].kind == DocumentFlowItemKind.DIALOGUE
    assert parsed_basic.flow[3].content == "Hi Bar"
    assert parsed_basic.flow[3].context.lineno == 6


def test_included_data(parsed_include: StagescriptParser) -> None:
    assert parsed_include.name == "test play"
    assert set(parsed_include.acts.keys()) == {"act", "another act"}
    assert set(parsed_include.scenes.keys()) == {"scene", "another scene"}
    assert len(parsed_include.characters) == 1
    assert parsed_include.characters["test"].handle == "test"
    assert parsed_include.characters["test"].name == "Test"
    assert parsed_include.characters["test"].introduce == "Test Testovich"
    assert parsed_include.metadata["key"].value == "value"


def test_compact(parsed_compact: StagescriptParser) -> None:
    compact_flow = parsed_compact.postprocess()
    assert len(parsed_compact.flow) > len(compact_flow)
    assert parsed_compact.flow[0].kind == DocumentFlowItemKind.STAGE_DIRECTION
    assert parsed_compact.flow[0].content == "I am doing something"
    assert parsed_compact.flow[1].kind == DocumentFlowItemKind.STAGE_DIRECTION
    assert parsed_compact.flow[1].content == "and I still am"

    assert compact_flow[0].kind == DocumentFlowItemKind.STAGE_DIRECTION
    assert compact_flow[0].content == "I am doing something and I still am"


def test_compact_double_newline_is_newline(parsed_compact: StagescriptParser) -> None:
    compact_flow = parsed_compact.postprocess()
    assert compact_flow[1].kind == DocumentFlowItemKind.SPEAKER
    assert compact_flow[2].kind == DocumentFlowItemKind.DIALOGUE
    assert compact_flow[2].content == "I am speaking.\nThis needs to be another line"


def test_unknown_function(script_unknown_function: Path) -> None:
    parser = StagescriptParser()
    with pytest.raises(ParsingError, match=".*Called to unknown function /nonexistent"):
        parser.parse(script_unknown_function)


def test_recursive_include(script_circular_include: Path) -> None:
    parser = StagescriptParser()
    with pytest.raises(ParsingError, match="Cannot process file .* - circular include"):
        parser.parse(script_circular_include)
