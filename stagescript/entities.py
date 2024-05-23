from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from stagescript.log import get_logger

logger = get_logger(__name__)

__all__ = [
    "Metadata",
    "Character",
    "LintingViolation",
    "LintingViolationSeverity",
    "Node",
    "Context",
    "NodeKind",
    "StageScript",
]


def _get_smart_starting_path(path: Path, relative_to: Path, symbol: str) -> Path:
    relative_parts = relative_to.parts
    if relative_parts == path.parts[: len(relative_parts)]:
        return symbol / path.relative_to(relative_to)
    return path


def get_condensed_path(path: Path) -> Path:
    home_path = _get_smart_starting_path(path, Path.home(), "~")
    cwd_path = _get_smart_starting_path(path, Path.cwd(), ".")
    return min((home_path, cwd_path, path), key=lambda pth: len(str(pth)))


@dataclass
class Context:
    path: Path
    lineno: int

    @property
    def link(self) -> str:
        """Return a link to the context's origin"""
        path = get_condensed_path(self.path)
        return f'File "{path.as_posix()}", line {self.lineno}'


class NodeKind(str, Enum):
    STAGE_DIRECTION = "stage_direction"
    DIALOGUE = "dialogue"
    SPEAKER = "speaker"
    MENTION = "mention"
    INLINE_STAGE_DIRECTION = "inline_stage_direction"
    PLAY = "play"
    ACT = "act"
    SCENE = "scene"
    DECLENSION = "declension"
    MENTION_WITH_DECLENSION = "mention_with_declension"
    TEXT = "text"


@dataclass(frozen=True, eq=True)
class Node:
    context: Context
    kind: NodeKind
    children: "list[Node]" = field(default_factory=list)
    text: str | None = None

    def __post_init__(self) -> None:
        if self.children and self.text:
            raise ValueError("Node cannot have both children and a text content")


@dataclass(frozen=True, eq=True)
class Character:
    handle: str
    name: str
    context: Context
    introduce: str | None = None


@dataclass(frozen=True, eq=True)
class Metadata:
    key: str
    value: str
    context: Context


class LintingViolationSeverity(str, Enum):
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, eq=True)
class LintingViolation:
    description: str
    context: Context
    severity: LintingViolationSeverity


def _iter_children(node: Node) -> Iterable[Node]:
    for child_node in node.children:
        if child_node.children:
            yield from _iter_children(child_node)
        else:
            yield child_node
    yield node


def _from_booly(value: str) -> bool:
    match value.lower().strip():
        case "true" | "yes" | "on":
            return True
        case "false" | "no" | "off":
            return False
        case "":
            return False
        case "1":
            return True
        case _:
            return False


@dataclass(frozen=True, eq=True)
class TemplateConfig:
    characters_sorted: bool = False
    break_after_act: bool = False
    direction_open: str = "("
    direction_close: str = ")"
    font_size: str = "12pt"

    @staticmethod
    def from_meta(meta: dict[str, Metadata]) -> "TemplateConfig":
        init_kwargs: dict[str, Any] = {}
        if "template-characters-sorted" in meta:
            init_kwargs["characters_sorted"] = _from_booly(meta["template-characters-sorted"].value)
        if "template-break-after-act" in meta:
            init_kwargs["break_after_act"] = _from_booly(meta["template-break-after-act"].value)
        if "template-direction-open" in meta:
            init_kwargs["direction_open"] = meta["template-direction-open"].value
        if "template-direction-close" in meta:
            init_kwargs["direction_close"] = meta["template-direction-close"].value
        if "template-font-size" in meta:
            init_kwargs["font_size"] = meta["template-font-size"].value
        logger.debug(init_kwargs)
        return TemplateConfig(**init_kwargs)


@dataclass(frozen=True, eq=True)
class StageScript:
    name: str | None = None
    metadata: dict[str, Metadata] = field(default_factory=dict)
    characters: dict[str, Character] = field(default_factory=dict)
    nodes: list[Node] = field(default_factory=list)
    violations: list[LintingViolation] = field(default_factory=list)
    template: TemplateConfig = field(default_factory=TemplateConfig)

    def __post_init__(self) -> None:
        # hehe
        if self.template == TemplateConfig():
            object.__setattr__(self, "template", TemplateConfig.from_meta(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def flatten(self) -> Iterable[Node]:
        """Iterates through nodes and their children"""
        for node in self.nodes:
            yield from _iter_children(node)

    @property
    def author(self) -> str | None:
        if "author" not in self.metadata:
            return None
        return self.metadata["author"].value

    @property
    def year(self) -> str | None:
        if "year" not in self.metadata:
            return None
        return self.metadata["year"].value

    @property
    def language(self) -> str:
        if "language" not in self.metadata:
            return "en"
        return self.metadata["language"].value
