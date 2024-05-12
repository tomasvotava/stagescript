from pathlib import Path

import pytest

from stagescript import StageScript, Tokenizer

_script_basic_content = {
    "test.play": "# test play\n/introduce foo; Foo; Foo, the Fooer\n/introduce bar; Bar; Bar, the Barer\n\n"
    "> @foo enters\n@foo: Hi Bar\n"
}

_script_include_content = {
    "test.play": """# test play\n/include included.play\n## another act\n### another scene\n""",
    "included.play": """## act\n### scene\n/introduce test; Test; Test Testovich\nkey: value\n""",
}

_script_compact_content = {
    "test.play": "# test play\n> I am doing something\nand I still am\n"
    "@tom: I am speaking.\n\nThis needs to be another line"
}

_script_all_features = {
    "test.play": """% This is the most awesome play in the world
# Test all features

/introduce tom; Tom; Tom is awesome
/introduce carl; Carl; Carl is just Carl

## Act One

### Scene one

> Both are sitting at the table. @carl stands up after a while.

@carl: I would like to know something.

@tom: {smiles} I know.

@carl: Well, at least you know.

@tom, @carl: {laugh} Hahaha.

/include included.play

@tom: This is the end
""",
    "included.play": "## Another act\n\n### Another scene\n",
}

_script_declension_content = {"test.play": """> Dívá se na @(Gertrudu)gertrude naštvaně\n"""}

_script_unknown_function = {"test.play": "# test play\n/nonexistent funuction"}

_script_unnamed_content = {"test.play": "/introduce foo; Mark; Mark is not a foo\n\n ## Act one"}

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
def script_basic(tmp_path: Path) -> Path:
    _create_path_structure(tmp_path, _script_basic_content)
    return tmp_path / "test.play"


@pytest.fixture()
def script_include(tmp_path: Path) -> Path:
    _create_path_structure(tmp_path, _script_include_content)
    return tmp_path / "test.play"


@pytest.fixture()
def script_compact(tmp_path: Path) -> Path:
    _create_path_structure(tmp_path, _script_compact_content)
    return tmp_path / "test.play"


@pytest.fixture()
def script_declension(tmp_path: Path) -> Path:
    _create_path_structure(tmp_path, _script_declension_content)
    return tmp_path / "test.play"


@pytest.fixture()
def script_unknown_function(tmp_path: Path) -> Path:
    _create_path_structure(tmp_path, _script_unknown_function)
    return tmp_path / "test.play"


@pytest.fixture()
def script_circular_include(tmp_path: Path) -> Path:
    _create_path_structure(tmp_path, _script_circular_include_content)
    return tmp_path / "test.play"


@pytest.fixture()
def script_unnamed(tmp_path: Path) -> Path:
    _create_path_structure(tmp_path, _script_unnamed_content)
    return tmp_path / "test.play"


@pytest.fixture()
def script_all_features(tmp_path: Path) -> Path:
    _create_path_structure(tmp_path, _script_all_features)
    return tmp_path / "test.play"


@pytest.fixture()
def parsed_basic(script_basic: Path) -> StageScript:
    return Tokenizer.parse(script_basic)


@pytest.fixture()
def parsed_include(script_include: Path) -> StageScript:
    return Tokenizer.parse(script_include)


@pytest.fixture()
def parsed_compact(script_compact: Path) -> StageScript:
    return Tokenizer.parse(script_compact)


@pytest.fixture()
def parsed_declension(script_declension: Path) -> StageScript:
    return Tokenizer.parse(script_declension)


@pytest.fixture()
def parsed_unnamed(script_unnamed: Path) -> StageScript:
    return Tokenizer.parse(script_unnamed)


@pytest.fixture()
def parsed_all_features(script_all_features: Path) -> StageScript:
    return Tokenizer.parse(script_all_features)
