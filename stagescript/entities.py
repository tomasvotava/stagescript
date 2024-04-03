from dataclasses import dataclass
from enum import Enum
from pathlib import Path


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
    lineno: int = 0
    pos: int = 0

    @property
    def link(self) -> str:
        """Return a link to the context's origin"""
        path = get_condensed_path(self.path)
        return f"File \"{path.as_posix()}, line {self.lineno}{':self.pos}' if self.pos else ''}\""


@dataclass
class Metadata:
    key: str
    value: str
    context: Context


@dataclass
class Character:
    handle: str
    name: str
    context: Context
    introduce: str | None = None


@dataclass
class Act:
    name: str
    context: Context


@dataclass
class Scene:
    name: str
    context: Context


class DocumentFlowItemKind(str, Enum):
    DIALOGUE = "dialogue"
    STAGE_DIRECTION = "stage_direction"
    INLINE_STAGE_DIRECTION = "inline_stage_direction"
    MENTION = "mention"
    SPEAKER = "speaker"
    ACT = "act"
    SCENE = "scene"


@dataclass
class DocumentFlowItem:
    context: Context
    kind: DocumentFlowItemKind
    content: str
