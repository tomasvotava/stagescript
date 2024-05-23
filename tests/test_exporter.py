import json
from pathlib import Path
from typing import Any

from stagescript import JSONExporter, MarkdownExporter, StageScript

# fmt: off
included_content_json = {"name":"test play","metadata":{"key":{"key":"key","value":"value"}},"characters":{"test":{"handle":"test","name":"Test","introduce":"Test Testovich"}},"nodes":[{"kind":"act","children":[{"kind":"text","children":[],"text":"act"},{"kind":"scene","children":[{"kind":"text","children":[],"text":"scene"}],"text":None}],"text":None},{"kind":"act","children":[{"kind":"text","children":[],"text":"another act"},{"kind":"scene","children":[{"kind":"text","children":[],"text":"another scene"}],"text":None}],"text":None}],"violations":[]}  # noqa: E501
# fmt: on

included_content_markdown = [
    "# Test all features",
    "## Act One",
    "### Scene one",
    "## Characters",
    "- Tom (Tom is awesome)",
    "- Carl (Carl is just Carl)",
    "> Both are sitting at the table. **Carl** stands up after a while.",
    "**Carl**: I would like to know something.",
    "**Tom, Carl**: (*laugh*) Hahaha.",
    "## Another act",
    "### Another scene",
    "**Tom**: (*smiles*) I know.",
]


def _remove_key_recursive(remove_key: str, dct: dict[str, Any]) -> None:
    if remove_key in dct:
        del dct[remove_key]
    for value in dct.values():
        if isinstance(value, dict):
            _remove_key_recursive(remove_key, value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _remove_key_recursive(remove_key, item)


def test_json_exporter(parsed_include: StageScript, tmp_path: Path) -> None:
    exporter = JSONExporter(parsed_include)
    exporter.export(tmp_path)
    result = tmp_path / "test-play.json"
    assert result.exists()
    with result.open("r", encoding="utf-8") as file:
        output = json.load(file)
    # remove "contexts", they contain absolute paths and would differ
    _remove_key_recursive("context", output)
    _remove_key_recursive("template", output)
    assert output == included_content_json


def test_exporter_default_name(parsed_unnamed: StageScript) -> None:
    exporter = JSONExporter(parsed_unnamed)
    assert exporter.file_basename is not None
    assert "-" in exporter.file_basename


def test_character_name(parsed_unnamed: StageScript) -> None:
    exporter = JSONExporter(parsed_unnamed)
    assert exporter.get_character_name("foo") == "Mark"
    assert exporter.get_character_name("bar") == "bar"


def test_markdown_exporter(parsed_all_features: StageScript, tmp_path: Path) -> None:
    exporter = MarkdownExporter(parsed_all_features)
    exporter.export(tmp_path)
    result = tmp_path / "test-all-features.md"
    assert result.exists()
    content = result.read_text().splitlines()
    for line in included_content_markdown:
        assert line in content
