from pathlib import Path
from typing import TextIO

from stagescript.entities import Node, NodeKind
from stagescript.export.base import Exporter
from stagescript.i18n import get_translation
from stagescript.types import guard

_ = get_translation()


class MarkdownExporter(Exporter):
    def _write_characters(self, file: TextIO) -> None:
        file.write("# ")
        file.write(self.script.name or _("Unnamed stageplay"))
        file.write("\n\n")
        if self.script.author is not None:
            file.write(_("by"))
            file.write(f" {self.script.author}\n\n")
        file.write("## ")
        file.write(_("Characters"))
        file.write("\n\n")
        for character in sorted(self.script.characters.values(), key=lambda character: character.name):
            file.write(f"- {character.name}")
            if character.introduce:
                file.write(f" ({character.introduce})")
            file.write("\n")
        file.write("\n")

    def _process_node(self, file: TextIO, node: Node) -> None:
        match node.kind:
            case NodeKind.TEXT:
                file.write(guard(node.text, str))
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
                file.write(f"\n\n**{speaker}**: ")
            case NodeKind.DIALOGUE:
                if not node.children:
                    file.write(node.text or "")
                for child_node in node.children:
                    self._process_node(file, child_node)
            case NodeKind.INLINE_STAGE_DIRECTION:
                file.write("(*")
                for child_node in node.children:
                    self._process_node(file, child_node)
                file.write("*)")
            case NodeKind.MENTION:
                name = self.get_character_name(guard(node.text, str))
                file.write(f"**{name}**")
            case NodeKind.STAGE_DIRECTION:
                file.write("> ")
                for child_node in node.children:
                    self._process_node(file, child_node)
                if node.text is not None:
                    file.write(node.text)

    def _export(self, path: Path) -> None:
        global _
        _ = get_translation(self.script.language)
        output = path / f"{self.file_basename}.md"
        with output.open(mode="w", encoding="utf-8") as file:
            self._write_characters(file)
            for node in self.script.nodes:
                self._process_node(file, node)
