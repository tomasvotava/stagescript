import re
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generator, Iterable, Protocol, TextIO

from stagescript.entities import (
    Act,
    Character,
    Context,
    DocumentFlowItem,
    DocumentFlowItemKind,
    Metadata,
    Scene,
)
from stagescript.log import get_logger

logger = get_logger()


class Pattern(str, Enum):
    pattern: re.Pattern[str]

    def __new__(cls, value: str, pattern: re.Pattern[str]) -> "Pattern":
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.pattern = pattern
        return obj

    function = ("function", re.compile(r"^\/(?P<function>\w+)(?:\s(?:.*))?$"))
    function_arguments = ("function_arguments", re.compile(r"(?:(?:\s)|(?:;\s?))(?P<argument>[^;]+)"))
    script_name = ("script_name", re.compile(r"^#\s?(?P<name>[^#]*)$"))
    act_name = ("act_name", re.compile(r"^##\s?(?P<name>[^#]*)$"))
    scene_name = ("scene_name", re.compile(r"^###\s?(?P<name>[^#]*)$"))
    metadata = ("metadata", re.compile(r"^(?P<key>[a-zA-Z0-9_\-]+):\s?(?P<value>.*)$"))
    comment = ("comment", re.compile(r"^%.*$"))
    dialogue_start = ("dialogue_start", re.compile(r"(?P<characters>@[a-zA-Z0-9]+(,\s?@[a-zA-Z0-9]+)*):"))
    dialogue_end = ("dialogue_end", re.compile(r"(?=(^(@[a-zA-Z0-9]+(,\s?@[a-zA-Z0-9]+)*):|^# |^## |^### |^> |^/|^%))"))
    stage_direction_start = ("stage_direction_start", re.compile(r"^> "))
    stage_direction_end = (
        "stage_direction_end",
        re.compile(r"(?=(^(@[a-zA-Z0-9]+(,\s?@[a-zA-Z0-9]+)*):|^# |^## |^### |^/|^%))"),
    )
    inline_stage_direction_start = ("inline_stage_direction_start", re.compile(r"{"))
    inline_stage_direction_end = ("inline_stage_direction_end", re.compile(r"}"))
    mention = ("mention", re.compile(r"(?P<mention>@[a-zA-Z0-9]+)"))

    @classmethod
    def by_name(cls, name: str) -> "Pattern":
        obj = getattr(cls, name, None)
        if not isinstance(obj, Pattern):
            raise AttributeError(f"No Pattern named {name!r} exists")
        return obj


class ParsingError(Exception):
    """Parsing error"""


class FunctionHandlerProtocol(Protocol):
    def __call__(self, *args: Any, context: Context) -> None: ...


def character_aware_join(sep: str, strings: Iterable[str]) -> str:
    line_breaks = {"broken": False}

    def _get_str(i: int, string: str) -> str:
        if i == 0:
            return string
        if not string:
            if not line_breaks["broken"]:
                line_breaks["broken"] = True
                return "\n"
            return ""
        if string[0].isalnum():
            if line_breaks["broken"]:
                line_breaks["broken"] = False
                return string
            return sep + string
        return string

    return "".join(_get_str(i, string) for i, string in enumerate(strings))


class StagescriptParser:
    def __init__(self) -> None:
        self.characters: dict[str, Character] = {}
        self.metadata: dict[str, Metadata] = {}
        self.acts: dict[str, Act] = {}
        self.scenes: dict[str, Scene] = {}
        self.name: str | None = None
        self.flow: list[DocumentFlowItem] = []
        self._current_act: Act | None = None
        self._current_scene: Scene | None = None
        self._function_handlers: dict[str, FunctionHandlerProtocol] = {}
        self._process_stack: list[Path] = []  # an include stack to check for circular includes

        self._register_function_handlers()

    def register_function_handler(self, function_name: str, handler: Callable[..., Any]) -> None:
        """Registers a handler for each time /{function_name} is encountered"""
        self._function_handlers[function_name] = handler

    def _register_function_handlers(self) -> None:
        self.register_function_handler("introduce", self.introduce_character)
        self.register_function_handler("include", self.include_file)

    def call_registered_function_handler(self, name: str, *args: Any, context: Context) -> None:
        if name not in self._function_handlers:
            raise ParsingError(f"{context.link} - Called to unknown function /{name}")
        logger.debug("%s - Called to function /%s (%s)", context.link, name, "; ".join(map(str, args)))
        func = self._function_handlers[name]
        return func(*args, context=context)

    def _check_stack(self, path: Path) -> bool:
        """Check and return whether the specified path is already in the stack."""
        matching = filter(path.samefile, self._process_stack)
        return bool(list(matching))

    @contextmanager
    def _enter_parsing(self, path: Path) -> Generator[TextIO, None, None]:
        if self._check_stack(path):
            raise ParsingError(
                f"Cannot process file {path} - circular include. "
                f"Check following stack for recursion:\n{' -> '.join(map(str, (*self._process_stack, path)))}"
            )
        self._process_stack.append(path)
        with path.open("r", encoding="utf-8") as file:
            yield file
        self._process_stack.remove(path)

    def _process_mentions(self, root_kind: DocumentFlowItemKind, line: str, context: Context) -> list[DocumentFlowItem]:
        """Process a line, find mentions, return all Flow items found"""
        sub_flow: list[DocumentFlowItem] = []
        for token in Pattern.mention.pattern.split(line):
            token = token.strip()
            if not token:
                continue
            if Pattern.mention.pattern.match(token):
                handle = token.lstrip("@")
                if handle not in self.characters:
                    logger.warning(
                        "%s - Character '%s' was mentioned that hasn't been properly introduced.", context.link, handle
                    )
                sub_flow.append(DocumentFlowItem(context=context, kind=DocumentFlowItemKind.MENTION, content=handle))
            else:
                sub_flow.append(DocumentFlowItem(context=context, kind=root_kind, content=token))
        return sub_flow

    def _process_dialogue_line(
        self, root_kind: DocumentFlowItemKind, line: str, context: Context
    ) -> list[DocumentFlowItem]:
        if root_kind not in (DocumentFlowItemKind.DIALOGUE, DocumentFlowItemKind.INLINE_STAGE_DIRECTION):
            logger.warning(
                "%s - Attempted to find inline directions outside of a dialogue. This is probably the parser's error."
            )
            return []
        other_kind = (
            DocumentFlowItemKind.INLINE_STAGE_DIRECTION
            if root_kind == DocumentFlowItemKind.DIALOGUE
            else DocumentFlowItemKind.DIALOGUE
        )
        next_pattern = (
            Pattern.inline_stage_direction_end
            if root_kind == DocumentFlowItemKind.INLINE_STAGE_DIRECTION
            else Pattern.inline_stage_direction_start
        )
        if (match := next_pattern.pattern.search(line)) is not None:
            startpos, endpos = match.span()
            rest = line[:startpos].strip()
            rest_flow = self._process_mentions(root_kind=root_kind, line=rest, context=context)
            return [
                *rest_flow,
                *self._process_dialogue_line(other_kind, line[endpos:].strip(), context=context),
            ]
        # The whole line is the same
        return [DocumentFlowItem(context=context, kind=root_kind, content=line.strip())]

    def parse(self, path: Path | str) -> None:
        path = Path(path).absolute()
        logger.debug("Parsing document %s", path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File {path} is not an existing file and cannot be parsed.")

        open_block_stack: list[DocumentFlowItemKind] = []
        # open_block_type: DocumentFlowItemKind | None = None
        with self._enter_parsing(path) as file:
            for lineno, line in enumerate(file):
                line = line.rstrip()
                context = Context(path=path, lineno=lineno + 1)
                if self.is_comment(line):
                    continue
                if open_block_stack and not line.strip():
                    # We need to keep empty lines for now so that we can compact them later
                    self.flow.append(DocumentFlowItem(context=context, kind=open_block_stack[-1], content=line.strip()))
                    continue
                if open_block_stack and open_block_stack[-1] == DocumentFlowItemKind.STAGE_DIRECTION:
                    if Pattern.stage_direction_end.pattern.match(line):
                        open_block_stack.pop()
                        # Continue parsing the line, it probably contains another pattern
                    else:
                        self.flow.extend(
                            self._process_mentions(DocumentFlowItemKind.STAGE_DIRECTION, line.strip(), context=context)
                        )
                        continue
                elif open_block_stack and open_block_stack[-1] == DocumentFlowItemKind.DIALOGUE:
                    if Pattern.dialogue_end.pattern.match(line):
                        open_block_stack.pop()
                        # Continue parsing the line, it probably contains another pattern
                    else:
                        self.flow.extend(
                            self._process_dialogue_line(DocumentFlowItemKind.DIALOGUE, line.strip(), context=context)
                        )
                        continue
                if (match := Pattern.script_name.pattern.match(line)) is not None:
                    self.update_name(match.group("name"), context=context)
                    continue
                if (match := Pattern.act_name.pattern.match(line)) is not None:
                    act_name = match.group("name").strip()
                    self.set_act(act_name, context=context)
                    self.flow.append(DocumentFlowItem(context=context, kind=DocumentFlowItemKind.ACT, content=act_name))
                    continue
                if (match := Pattern.scene_name.pattern.match(line)) is not None:
                    scene_name = match.group("name")
                    self.set_scene(scene_name, context=context)
                    self.flow.append(
                        DocumentFlowItem(context=context, kind=DocumentFlowItemKind.SCENE, content=scene_name)
                    )
                    continue
                if (match := Pattern.metadata.pattern.match(line)) is not None:
                    self.update_metadata(match, context=context)
                    continue
                if (match := Pattern.function.pattern.match(line)) is not None:
                    arguments = Pattern.function_arguments.pattern.findall(line)
                    self.call_registered_function_handler(match.group("function"), *arguments, context=context)
                    continue
                if (match := Pattern.stage_direction_start.pattern.match(line)) is not None:
                    stage_direction = Pattern.stage_direction_start.pattern.sub("", line)
                    open_block_stack.append(DocumentFlowItemKind.STAGE_DIRECTION)
                    self.flow.extend(
                        self._process_mentions(
                            DocumentFlowItemKind.STAGE_DIRECTION, stage_direction.strip(), context=context
                        )
                    )
                    continue
                if (match := Pattern.dialogue_start.pattern.match(line)) is not None:
                    for speaker in match.group("characters").split(","):
                        speaker = speaker.strip().lstrip("@")
                        if speaker not in self.characters:
                            logger.warning(
                                "%s - Character '%s' speaks but hasn't been properly introduced", context.link, speaker
                            )
                        self.flow.append(
                            DocumentFlowItem(context=context, kind=DocumentFlowItemKind.SPEAKER, content=speaker)
                        )
                    # remove speaker from the line
                    dialogue = Pattern.dialogue_start.pattern.sub("", line)
                    parsed_lines = self._process_dialogue_line(DocumentFlowItemKind.DIALOGUE, dialogue, context=context)
                    self.flow.extend(parsed_lines)
                    if parsed_lines:
                        open_block_stack.append(parsed_lines[-1].kind)
                    continue

    def introduce_character(self, handle: str, name: str, introduce: str | None = None, *, context: Context) -> None:
        """Called when /introduce function is encountered"""
        logger.info("%s - Introducing character %s (@%s) as: %s", context.link, name, handle, introduce)
        character = Character(handle=handle, name=name, introduce=introduce, context=context)
        self.characters[handle] = character

    def include_file(self, relative_path: str, *, context: Context) -> None:
        """Include another file as if its contents were copied into the one currently being parsed.

        The path is relative to the path being processed.
        """
        current_path = self._process_stack[-1]
        include_path = (current_path.parent / relative_path).resolve()
        logger.info("%s - Include file %s", context.link, include_path)
        self.parse(include_path)

    def is_comment(self, line: str) -> bool:
        """Checks whether current line is commented out"""
        return line.startswith("%")

    def update_name(self, name: str, context: Context) -> None:
        """Called when '# Script name' encountered"""
        if self.name is not None:
            logger.warning("%s - Overwriting current script name %s -> %s", context.link, self.name, name)
        self.name = name

    def set_act(self, name: str, context: Context) -> None:
        """Called when '## Act name' encountered"""
        if name in self.acts:
            logger.warning(
                "%s - Duplicate act '%s' was previously created in %s. This will result in a strange behavior.",
                context.link,
                name,
                self.acts[name].context.link,
            )
        act = Act(name=name, context=context)
        self.acts[name] = act
        self.set_current_act(act)

    def set_current_act(self, act: Act) -> None:
        if self._current_act is not None:
            logger.debug("%s - Closing act '%s'", act.context.link, self._current_act.name)
        logger.debug("%s - Entering act '%s'", act.context.link, act.name)
        self._current_act = act

    def set_scene(self, name: str, context: Context) -> None:
        """Called when '### Scene name' encountered"""
        if name in self.scenes:
            logger.warning(
                "%s - Duplicate scene '%s' was previously created in %s. This will result in a strange behavior",
                context.link,
                name,
                self.scenes[name].context.link,
            )
        scene = Scene(name=name, context=context)
        self.scenes[name] = scene
        self.set_current_scene(scene)

    def set_current_scene(self, scene: Scene) -> None:
        if self._current_scene is not None:
            logger.debug("%s - Closing scene '%s'", scene.context.link, self._current_scene.name)
        logger.debug("%s - Entering scene '%s'", scene.context.link, scene.name)
        self._current_scene = scene

    def update_metadata(self, match: re.Match[str], context: Context) -> None:
        key, value = match.group("key"), match.group("value")
        if key in self.metadata:
            original_context = self.metadata[key].context
            logger.warning(
                "%s - Overriding metadata key %s (previously set in %s)", context.link, key, original_context.link
            )
        self.metadata[key] = Metadata(key=key, value=value, context=context)

    def _compact(self, flow: list[DocumentFlowItem]) -> list[DocumentFlowItem]:
        """Compact the flow"""
        compacted_flow: list[DocumentFlowItem] = []
        doc_index = 0
        compactible_kinds: tuple[DocumentFlowItemKind, ...] = (
            DocumentFlowItemKind.DIALOGUE,
            DocumentFlowItemKind.INLINE_STAGE_DIRECTION,
            DocumentFlowItemKind.STAGE_DIRECTION,
        )
        while doc_index < len(flow):
            document = flow[doc_index]
            if document.kind not in compactible_kinds:
                compacted_flow.append(document)
                doc_index += 1
                continue
            related_documents: list[DocumentFlowItem] = []
            for related_document in self.flow[doc_index + 1 :]:
                if related_document.kind == document.kind:
                    related_documents.append(related_document)
                else:
                    break
            if not related_documents:
                compacted_flow.append(document)
                doc_index += 1
                continue
            joined_document = DocumentFlowItem(
                context=document.context,
                kind=document.kind,
                content=character_aware_join(" ", (doc.content.strip() for doc in (document, *related_documents))),
            )
            logger.debug("%s - Compacting %d items together", document.context.link, len(related_documents) + 1)
            compacted_flow.append(joined_document)
            doc_index += len(related_documents) + 1
        return compacted_flow

    def postprocess(self) -> list[DocumentFlowItem]:
        """Postprocess the flow"""
        return self._compact(self.flow)


if __name__ == "__main__":

    parser = StagescriptParser()
    parser.parse("./examples/hamlet.play")
    # try:
    #     parser.parse("./examples/recursion/main.play")
    # except ParsingError as error:
    #     logging.error(str(error))

    logger.debug(parser.name)
    logger.debug(parser.metadata)
    flow = parser.postprocess()
    for doc in flow:
        logger.debug(f"{doc.context.lineno:03} {doc.kind.name} {doc.content}")
