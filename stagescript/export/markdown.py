from pathlib import Path
from typing import TextIO

from stagescript.entities import Node, NodeKind
from stagescript.export.base import Exporter
from stagescript.types import guard


class MarkdownExporter(Exporter):
    def _write_characters(self, file: TextIO) -> None:
        file.write(f"# {self.script.name or 'Unnamed stageplay'}\n\n")
        file.write("## Characters\n\n")
        for character in sorted(self.script.characters.values(), key=lambda character: character.name):
            file.write(f"- {character.name}")
            if character.introduce:
                file.write(f" ({character.introduce})")
            file.write("\n")
        file.write("\n")

    def _process_node(self, file: TextIO, node: Node) -> None:
        match node.kind:
            case NodeKind.TEXT:
                assert node.text is not None
                file.write(node.text)
            case NodeKind.ACT:
                file.write(f"\n## {node.children[0].text}\n")
                for child_node in node.children[1:]:
                    self._process_node(file, child_node)
            case NodeKind.SCENE:
                file.write(f"\n### {node.children[0].text}\n")
                for child_node in node.children[1:]:
                    self._process_node(file, child_node)
            case NodeKind.SPEAKER:
                if node.children:
                    try:
                        speaker = ", ".join(
                            self.get_character_name(guard(child_node.text, str)) for child_node in node.children
                        )
                    except TypeError as error:
                        raise ValueError(
                            f"{node.context.link} - Parsed script is invalid, "
                            "one or more of mentioned speakers were empty"
                        ) from error
                else:
                    if node.text is None:
                        raise ValueError(
                            f"{node.context.link} - Parsed script is invalid, "
                            "SPEAKER node is neither parent nor a child."
                        )
                    speaker = self.get_character_name(node.text)
                file.write(f"\n\n**{speaker}**:")
            case NodeKind.DIALOGUE:
                for child_node in node.children:
                    self._process_node(file, child_node)
                else:
                    file.write(node.text or "")
            case NodeKind.INLINE_STAGE_DIRECTION:
                file.write("(*")
                for child_node in node.children:
                    self._process_node(file, child_node)
                file.write("*)")
            case NodeKind.MENTION:
                assert node.text is not None
                name = self.get_character_name(node.text)
                file.write(f"**{name}**")
            case NodeKind.STAGE_DIRECTION:
                file.write("> ")
                for child_node in node.children:
                    self._process_node(file, child_node)
                else:
                    if node.text is not None:
                        file.write(node.text)

    def export(self, path: Path | str) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        output = path / f"{self.file_basename}.md"
        with output.open(mode="w", encoding="utf-8") as file:
            self._write_characters(file)
            for node in self.script.nodes:
                self._process_node(file, node)
