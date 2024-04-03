from pathlib import Path
from typing import Generator

import pytest

from stagescript.parser import StagescriptParser

_script_basic_content = {
    "test.play": """# test play\n/introduce foo; Foo; Foo, the Fooer\n/introduce bar; Bar; Bar, the Barer\n\n> @foo enters\n@foo: Hi Bar\n"""
}

_script_include_content = {
    "test.play": """# test play\n/include included.play\n## another act\n### another scene\n""",
    "included.play": """## act\n### scene\n/introduce test; Test; Test Testovich\nkey: value\n""",
}

_script_compact_content = {
    "test.play": """# test play\n> I am doing something\nand I still am\n@tom: I am speaking.\n\nThis needs to be another line"""
}

_script_unknown_function = {"test.play": "# test play\n/nonexistent funuction"}

_script_circular_include_content = {
    "test.play": "/include metadata.play",
    "metadata.play": "key: value\n/include recurse.play",
    "recurse.play": "/include test.play",
}


def _create_path_structure(path: Path, content: dict[str, str]) -> None:
    for name, script in content.items():
        script_path = path / name
        script_path.write_text(script, encoding="utf-8")


@pytest.fixture()
def script_basic(tmp_path: Path) -> Generator[Path, None, None]:
    _create_path_structure(tmp_path, _script_basic_content)
    yield tmp_path / "test.play"


@pytest.fixture()
def script_include(tmp_path: Path) -> Generator[Path, None, None]:
    _create_path_structure(tmp_path, _script_include_content)
    yield tmp_path / "test.play"


@pytest.fixture()
def script_compact(tmp_path: Path) -> Generator[Path, None, None]:
    _create_path_structure(tmp_path, _script_compact_content)
    yield tmp_path / "test.play"


@pytest.fixture()
def script_unknown_function(tmp_path: Path) -> Generator[Path, None, None]:
    _create_path_structure(tmp_path, _script_unknown_function)
    yield tmp_path / "test.play"


@pytest.fixture()
def script_circular_include(tmp_path: Path) -> Generator[Path, None, None]:
    _create_path_structure(tmp_path, _script_circular_include_content)
    yield tmp_path / "test.play"


@pytest.fixture()
def parsed_basic(script_basic: Path) -> StagescriptParser:
    parser = StagescriptParser()
    parser.parse(script_basic)
    return parser


@pytest.fixture()
def parsed_include(script_include: Path) -> StagescriptParser:
    parser = StagescriptParser()
    parser.parse(script_include)
    return parser


@pytest.fixture()
def parsed_compact(script_compact: Path) -> StagescriptParser:
    parser = StagescriptParser()
    parser.parse(script_compact)
    return parser
