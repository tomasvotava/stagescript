import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Literal

from odf.opendocument import OpenDocument, OpenDocumentText
from odf.style import (
    Element,
    MasterPage,
    PageLayout,
    PageLayoutProperties,
    ParagraphProperties,
    Style,
    TabStop,
    TabStops,
    TextProperties,
)
from odf.text import H, P, Tab
from odf.text import Span as ODFSpan

from stagescript.entities import Node, NodeKind, StageScript
from stagescript.i18n import get_translation
from stagescript.log import get_logger

from .base import Exporter

logger = get_logger(__name__)

_ = get_translation()

size_re = re.compile(r"(?P<size>\d+)(?P<unit>\w+)")

defaults: dict[str, Any] = {
    "page": {
        "width": "210mm",
        "height": "297mm",
        "orientation": "portrait",
        "margin": {
            "left": "20mm",
            "right": "20mm",
            "top": "20mm",
            "bottom": "20mm",
        },
    },
    "font": {"family": "Times New Roman", "size": 12},
}

# when int, best unit is guessed (pt for text, mm for everything else)
Size = int | str


def _to_size(size: str | int, text: bool = False) -> str:
    """Convert to size with a unit"""
    if isinstance(size, str):
        # already contains unit, hopefully
        return size
    unit = "pt" if text else "mm"
    return f"{size}{unit}"


@dataclass
class TextStyle:
    name: str
    size: int | str
    weight: Literal["bold", "normal"] = "normal"
    italic: bool = False
    font_family: str = defaults["font"]["family"]

    @property
    def text_properties(self) -> Element:
        properties = TextProperties(
            attributes={"fontsize": _to_size(self.size, text=True), "fontname": self.font_family}
        )
        if self.weight != "normal":
            properties.setAttribute("fontweight", self.weight)
        if self.italic:
            properties.setAttribute("fontstyle", "italic")
        return properties

    @cached_property
    def element(self) -> Element:
        style_entity = Style(name=self.name, family="text")
        properties = self.text_properties
        style_entity.addElement(properties)
        return style_entity


@dataclass
class ParagraphStyle:
    text_style: TextStyle
    align: Literal["left", "right", "center"] = "left"
    vertical_align: Literal["middle"] | None = None
    margin_top: int | str | None = None
    margin_bottom: int | str | None = None
    tab_stop: int | str | None = None
    break_before: bool = False
    middle_top_margin: str = "0mm"

    def __post_init__(self) -> None:
        if self.vertical_align is not None and self.margin_top is not None:
            logger.warning(
                f"Style {self.text_style.name!r} has both vertical align and top margin set. Margin will be ignored."
            )

    @property
    def paragraph_properties(self) -> Element:
        properties = ParagraphProperties()
        properties.setAttribute("textalign", self.align)
        if self.vertical_align == "middle":
            logger.debug(f"{self.text_style.name}, mt: {self.middle_top_margin}")
            properties.setAttribute("margintop", self.middle_top_margin)
        elif self.margin_top is not None:
            properties.setAttribute("margintop", _to_size(self.margin_top))
        if self.margin_bottom is not None:
            properties.setAttribute("marginbottom", _to_size(self.margin_bottom))
        if self.tab_stop is not None:
            tab_stop = _to_size(self.tab_stop)
            properties.setAttribute("tabstopdistance", tab_stop)
            properties.setAttribute("marginleft", tab_stop)
            properties.setAttribute("textindent", f"-{tab_stop}")
            tab_stops = TabStops()
            tab_stops.addElement(TabStop(position=tab_stop, type="left"))
            properties.addElement(tab_stops)
        if self.break_before:
            properties.setAttribute("breakbefore", "page")
        return properties

    @cached_property
    def element(self) -> Element:
        style_entity = Style(name=self.text_style.name, family="paragraph")
        style_entity.addElement(self.text_style.text_properties)
        style_entity.addElement(self.paragraph_properties)
        return style_entity


class Styles:
    def __init__(
        self, font_family: str | None = None, font_size: int | str | None = None, middle_top_margin: str = "0mm"
    ) -> None:
        font_family = font_family or defaults["font"]["family"]
        font_size = font_size or defaults["font"]["size"]
        self.play_title = ParagraphStyle(
            TextStyle("Play Title", 32, "bold", font_family=font_family),
            align="center",
            vertical_align="middle",
            middle_top_margin=middle_top_margin,
        )
        self.play_subtitle = ParagraphStyle(
            TextStyle("Play Subtitle", font_size, font_family=font_family), align="center"
        )
        self.act_title = ParagraphStyle(TextStyle("Act Title", 18, "bold", font_family=font_family), align="center")
        self.scene_title = ParagraphStyle(
            TextStyle("Scene Title", 16, "bold", font_family=font_family), align="center", margin_top="5mm"
        )
        self.script = ParagraphStyle(TextStyle("Script", font_size, font_family=font_family))
        self.character = TextStyle("Character", font_size, "bold", font_family=font_family)
        self.stage_direction = ParagraphStyle(
            TextStyle("Stage Direction", font_size, italic=False, font_family=font_family),
            margin_top="7mm",
            margin_bottom="7mm",
        )
        self.dialogue = ParagraphStyle(
            TextStyle("Dialogue", font_size, font_family=font_family), tab_stop=25, margin_top="0mm"
        )
        self.page_break = ParagraphStyle(TextStyle("Page Break", 1, font_family=font_family), break_before=True)

    def to_dict(self) -> dict[str, TextStyle | ParagraphStyle]:
        return {attr: value for attr, value in self.__dict__.items() if isinstance(value, TextStyle | ParagraphStyle)}


@dataclass
class Span:
    content: str
    style: TextStyle | None = None

    @cached_property
    def element(self) -> Element:
        kwargs = {"stylename": self.style.element} if self.style else {}
        return ODFSpan(text=self.content, **kwargs)


@dataclass
class Paragraph:
    content: list[str | Span] = field(default_factory=list)
    style = ParagraphStyle

    @cached_property
    def element(self) -> Element:
        paragraph = P(stylename=self.style.element)
        for token in self.content:
            if isinstance(token, str):
                paragraph.addText(token)
            else:
                paragraph.addElement(token.element)


@dataclass
class Dialogue:
    speakers: list[str]
    content: list[Span | None]
    speaker_style: TextStyle
    paragraph_style: ParagraphStyle

    @cached_property
    def elements(self) -> list[Element]:
        paragraphs = []
        paragraph = P(stylename=self.paragraph_style.element)
        speakers = ", ".join(self.speakers)
        paragraph.addElement(ODFSpan(stylename=self.speaker_style.element, text=speakers))
        paragraph.addElement(Tab())
        for span in self.content:
            if isinstance(span, Span):
                paragraph.addElement(span.element)
            elif span is None:
                paragraphs.append(paragraph)
                paragraph = P(stylename=self.paragraph_style.element)
                paragraph.addElement(Tab())
        paragraphs.append(paragraph)
        return paragraphs


def _get_from_defaults(key: str) -> str:
    dct = defaults
    for part in key.split("-"):
        if not isinstance(dct, dict):
            raise ValueError(f"Key {key!r} does not exist")
        dct = dct[part]
    if not isinstance(dct, str):
        raise ValueError(f"Key {key!r} is not a whole default path")
    return dct


class ODFTextExporter(Exporter):
    def __init__(self, script: StageScript) -> None:
        global _
        super().__init__(script)
        _ = get_translation(self.script.language)
        self._styles: Styles | None = None
        self._document = self._create_document()
        self._opened_paragraph: Element | None = None
        self._opened_dialogue: Dialogue | None = None

    @property
    def styles(self) -> Styles:
        if self._styles is None:
            raise RuntimeError("Styles were not initialized yet.")
        return self._styles

    def _from_meta(self, key: str) -> str:
        default = _get_from_defaults(key)
        metadata = self.script.metadata.get(key)
        if metadata is None:
            return default
        return metadata.value

    def _get_page_layout_properties(self) -> Element:
        return PageLayoutProperties(
            pagewidth=self._from_meta("page-width"),
            pageheight=self._from_meta("page-height"),
            printorientation=self._from_meta("page-orientation"),
            marginleft=self._from_meta("page-margin-left"),
            marginright=self._from_meta("page-margin-right"),
            margintop=self._from_meta("page-margin-top"),
            marginbottom=self._from_meta("page-margin-bottom"),
        )

    def _get_meta_size(self, prop: str) -> tuple[int, str]:
        meta_value = self._from_meta(prop)
        if (meta_match := size_re.match(meta_value)) is None:
            logger.warning(f"Failed to parse meta property {prop!r} value of {meta_value!r}.")
            return (0, "mm")
        return (int(meta_match.group("size")), meta_match.group("unit"))

    @cached_property
    def _font_family(self) -> str:
        return self._from_meta("font-family")

    @cached_property
    def _middle_top_margin(self) -> str:
        page_height, page_units = self._get_meta_size("page-height")
        margin_top, margin_top_units = self._get_meta_size("page-margin-top")
        if page_units != margin_top_units:
            logger.warning(
                f"Units mismatch, page height is measured in {page_units}, top margin in {margin_top_units}."
            )
            margin_top = 0
        return f"{(page_height // 4) + margin_top}{page_units}"

    def _define_styles(self, document: OpenDocument) -> None:
        self._styles = Styles(
            font_family=self._font_family,
            font_size=self.script.template.font_size,
            middle_top_margin=self._middle_top_margin,
        )
        for style_name, config in self._styles.to_dict().items():
            logger.debug(f"Creating style {style_name!r} ({config.__class__.__name__})")
            document.styles.addElement(config.element)

    def _create_title(self) -> None:
        self._document.text.addElement(
            H(stylename=self.styles.play_title.element, text=self.script.name, outlinelevel=1)
        )
        if self.script.author is not None:
            self._document.text.addElement(P(stylename=self.styles.play_subtitle.element, text=self.script.author))
        if self.script.year is not None:
            self._document.text.addElement(P(stylename=self.styles.play_subtitle.element, text=self.script.year))

    def _break_page(self) -> None:
        self._document.text.addElement(P(stylename=self.styles.page_break.element))

    def _create_characters_list(self) -> None:
        self._break_page()
        self._document.text.addElement(H(stylename=self.styles.act_title.element, text=_("Characters"), outlinelevel=2))
        characters = list(self.script.characters.values())
        if self.script.template.characters_sorted:
            characters = sorted(self.script.characters.values(), key=lambda char: char.name)
        for character in characters:
            character_paragraph = P(stylename=self.styles.dialogue.element)
            character_paragraph.addElement(ODFSpan(stylename=self.styles.character.element, text=character.name))
            character_paragraph.addElement(Tab())
            if character.introduce:
                character_paragraph.addElement(ODFSpan(text=character.introduce))
            self._document.text.addElement(character_paragraph)

    def _create_document(self) -> OpenDocument:
        document = OpenDocumentText()
        page_layout_properties = self._get_page_layout_properties()
        page_layout = PageLayout(name="pagelayout")
        page_layout.addElement(page_layout_properties)
        document.automaticstyles.addElement(page_layout)
        master_page = MasterPage(name="Standard", pagelayoutname=page_layout)
        document.masterstyles.addElement(master_page)
        self._define_styles(document)
        return document

    @property
    def opened_paragraph(self) -> Element:
        if self._opened_paragraph is None:
            raise RuntimeError("No paragraph was open.")
        return self._opened_paragraph

    def open_paragraph(self, stylename: Element) -> Element:
        if self._opened_paragraph is not None:
            raise RuntimeError("A paragraph was already opened.")
        self._opened_paragraph = P(stylename=stylename)
        return self._opened_paragraph

    def close_paragraph(self) -> None:
        if self._opened_paragraph is None:
            raise RuntimeError("No paragraph was open.")
        self._document.text.addElement(self._opened_paragraph)
        self._opened_paragraph = None

    @property
    def opened_dialogue(self) -> Dialogue:
        if self._opened_dialogue is None:
            raise RuntimeError("No dialogue was open.")
        return self._opened_dialogue

    def start_dialogue(self, speakers: list[str]) -> Dialogue:
        if self._opened_dialogue is not None:
            raise RuntimeError("A dialogue was already opened.")
        self._opened_dialogue = Dialogue(
            speakers=speakers, content=[], speaker_style=self.styles.character, paragraph_style=self.styles.dialogue
        )
        return self._opened_dialogue

    def end_dialogue(self) -> None:
        if self._opened_dialogue is None:
            raise RuntimeError("No dialogue was open")
        for paragraph in self._opened_dialogue.elements:
            self._document.text.addElement(paragraph)
        self._opened_dialogue = None

    def _process_flow(self, node: Node, paragraph: Element | None = None) -> None:
        match node.kind:
            case NodeKind.SPEAKER:
                self.start_dialogue([self.get_character_name(child.text) for child in node.children])
            case NodeKind.STAGE_DIRECTION:
                self.open_paragraph(self.styles.stage_direction.element)
                for child in node.children:
                    self._process_flow(child)
                self.close_paragraph()
            case NodeKind.TEXT:
                if node.text is not None and node.text.strip():
                    if self._opened_dialogue:
                        self.opened_dialogue.content.append(Span(node.text))
                    elif self._opened_paragraph:
                        self.opened_paragraph.addElement(ODFSpan(text=node.text))
                    else:
                        raise RuntimeError("No dialogue nor paragraph was opened.")
            case NodeKind.DIALOGUE:
                if node.text is not None:
                    # We are inside a dialogue node
                    for lineno, line in enumerate(node.text.split("\n")):
                        self.opened_dialogue.content.append(Span(line))
                        if lineno != len(line) - 1:
                            self.opened_dialogue.content.append(None)
                    return
                # This a dialogue node root that will contain the text as its children
                for child in node.children:
                    self._process_flow(child)
                self.end_dialogue()
            case NodeKind.INLINE_STAGE_DIRECTION:
                self.opened_dialogue.content.append(
                    Span(
                        self.script.template.direction_open,
                    )
                )
                for child in node.children:
                    self._process_flow(child)
                self.opened_dialogue.content.append(Span(self.script.template.direction_close))
            case NodeKind.MENTION_WITH_DECLENSION:
                if len(node.children) != 2:
                    logger.warning("Mention with declension has unexpected child nodes.")
                    return
                if self._opened_dialogue:
                    self._opened_dialogue.content.append(
                        Span(
                            node.children[1].text or self.get_character_name(node.children[0].text),
                            self.styles.character,
                        )
                    )
                elif self._opened_paragraph:
                    self.opened_paragraph.addElement(
                        ODFSpan(stylename=self.styles.character.element, text=node.children[1].text)
                    )
                else:
                    raise RuntimeError("No dialogue nore paragraph was opened.")
            case NodeKind.MENTION:
                if self._opened_dialogue:
                    self.opened_dialogue.content.append(Span(self.get_character_name(node.text), self.styles.character))
                elif self._opened_paragraph:
                    self.opened_paragraph.addElement(
                        ODFSpan(stylename=self.styles.character.element, text=self.get_character_name(node.text))
                    )
                else:
                    raise RuntimeError("No dialogue nor paragraph was opened.")
            case _:
                logger.warning(f"Node kind {node.kind!r} is not yet supported.")
                self._document.text.addElement(
                    P(stylename=self.styles.script.element, text=f"{node.kind=}, {node.text=}, {node.children=}")
                )

    def _process_scene(self, scene: Node) -> None:
        if not scene.children:
            logger.warning(f"Scene {scene.text!r} has no children, this is weird.")
            return
        for child_id, child in enumerate(scene.children):
            if child_id == 0:
                # This must be the scene's name, if not it's weird
                if child.kind != NodeKind.TEXT or child.text is None:
                    logger.warning(f"Scene {scene.text!r} has no name, this is very weird, but I'll continue.")
                else:
                    self._document.text.addElement(
                        H(stylename=self.styles.scene_title.element, text=child.text, outlinelevel=3)
                    )
                    continue
            self._process_flow(child)

    def _process_act(self, act: Node) -> None:
        if not act.children:
            logger.warning(f"Act {act.text!r} has no children, this is weird.")
            return
        self._break_page()
        scenes_processed = 0
        for child_id, child in enumerate(act.children):
            if child_id == 0:
                # This must be the act's name, if not it's weird
                if child.kind != NodeKind.TEXT or child.text is None:
                    logger.warning(f"Act {act.text!r} has no name, this is very weird, but I'll continue.")
                else:
                    self._document.text.addElement(
                        H(stylename=self.styles.act_title.element, text=child.text, outlinelevel=2)
                    )
                    continue
            if child.kind == NodeKind.SCENE:
                if scenes_processed != 0:
                    self._break_page()
                self._process_scene(child)
                scenes_processed += 1
                continue
            self._process_flow(child)
        if self.script.template.break_after_act:
            self._break_page()

    def _process_nodes(self) -> None:
        for node in self.script.nodes:
            match node.kind:
                case NodeKind.ACT:
                    self._process_act(node)
                case default:
                    logger.warning(f"Unsupported node kind {default}.")

    def _export(self, path: Path) -> None:
        output_path = (path / self.file_basename).with_suffix(".odt")
        self._create_title()
        self._create_characters_list()
        self._process_nodes()
        self._document.save(output_path.as_posix())
