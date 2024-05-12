import inspect
import logging
import re
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from stagescript.entities import (
    Character,
    Context,
    LintingViolation,
    LintingViolationSeverity,
    Metadata,
    Node,
    NodeKind,
    StageScript,
)
from stagescript.log import get_logger

logger = get_logger(__name__)

stop_pattern = r"(?=(?:^@[a-zA-Z0-9]+(?:,\s?@[a-zA-Z0-9]+)*:)|(?:^#)|(?:^\/)|(?:^%)|(?:\Z)|(?:^>\s))"

toplevel_patterns: dict[str, str] = {
    "function": r"^/(?P<function>\w+)(?:\s(?P<function_arguments>.*))?$",
    "play_name": r"^#\s?(?P<play_name>[^#]*?)$",
    "act_name": r"^##\s?(?P<act_name>[^#]*?)$",
    "scene_name": r"^###\s?(?P<scene_name>[^#]*?)$",
    "metadata": r"^(?P<key>[a-zA-Z0-9_\-]+):\s?(?P<value>.*)$",
    "stage_direction": r"^>\s(?P<stage_direction>.*)$",
    "dialogue": rf"^(?P<speaker>@[a-zA-Z0-9]+(?:,\s?@[a-zA-Z0-9]+)*):\s?(?P<dialogue>(?:.|\s)+?){stop_pattern}",
}


dialogue_sub_patterns = re.compile(r"\{(?P<inline_stage_direction>[^}]+)\}|(?P<dialogue>[^{}]+)", re.MULTILINE)
stage_direction_sub_patterns = re.compile(
    r"@(?P<mention>(?P<declension>\([^\)]+\))?[a-zA-Z0-9]+)|(?P<stage_direction>(?<!@)[^@]+)"
)
declension_sub_pattern = re.compile(r"\((?P<declension>[^\)]+)\)(?P<character>[a-zA-Z0-9]+)")


class ParsingError(ValueError): ...


class Tokenizer:
    pattern_toplevel = re.compile("|".join(toplevel_patterns.values()), re.MULTILINE)

    # can be found within dialogue
    pattern_inline_stage_direction = re.compile(r"\{(?P<inline_stage_direction>[^}]+)\}", re.MULTILINE)

    # can be found within inline/block stage direction
    pattern_mention = re.compile(r"@(?P<mention>[a-zA-Z0-9]+)", re.MULTILINE)

    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.metadata: dict[str, Metadata] = {}
        self.characters: dict[str, Character] = {}
        self.play_name: str | None = None
        self.violations: list[LintingViolation] = []
        self._include_stack: list[str] = []
        self._functions: dict[str, Callable[..., None | Iterable[Node]]] = {}
        self._register_handlers()
        self._current_act: Node | None = None
        self._current_scene: Node | None = None

    def track_violation(
        self,
        description: str,
        context: Context,
        severity: LintingViolationSeverity = LintingViolationSeverity.WARNING,
        log: bool = True,
    ) -> None:
        self.violations.append(LintingViolation(description, context, severity))
        if not log:
            return
        loglevel: int
        match severity:
            case LintingViolationSeverity.WARNING:
                loglevel = logging.WARNING
            case LintingViolationSeverity.ERROR:
                loglevel = logging.ERROR
            case _:
                loglevel = logging.ERROR
        logger.log(loglevel, "%s - %s", context.link, description)

    @property
    def valid(self) -> bool:
        """Returns True if the tokenizer parsing passes"""
        return not list(filter(lambda violation: violation.severity == LintingViolationSeverity.ERROR, self.violations))

    def _register_handlers(self) -> None:
        self._functions["introduce"] = self._handle_introduce
        self._functions["include"] = self._handle_include

    def _handle_introduce(self, handle: str, name: str, introduce: str | None = None, *, context: Context) -> None:
        logger.info("%s - Introducing %s (%s) as %s", context.link, name, handle, introduce)
        if handle in self.characters:
            self.track_violation(
                f"Character handle {handle} was previously introduced in {self.characters[handle].context.link}",
                context,
            )
        self.characters[handle] = Character(handle=handle, name=name, context=context, introduce=introduce)

    @contextmanager
    def _check_include_stack(self, path: Path, context: Context) -> Iterator[bool]:
        if path.as_posix() in self._include_stack:
            self.track_violation(
                f"Cannot process file {path} - circular include",
                context=context,
                severity=LintingViolationSeverity.ERROR,
            )
            yield False
        else:
            self._include_stack.append(path.as_posix())
            yield True
            self._include_stack.pop()

    def _handle_include(self, include_path: str, *, context: Context) -> Iterable[Node]:
        path = (context.path.parent / include_path).resolve()
        if not path.exists() or not path.is_file():
            self.track_violation(
                f"Included path {include_path} is not an existing file",
                context,
                LintingViolationSeverity.ERROR,
                log=self.dry_run,  # only log if no exception is to be raised
            )
            if self.dry_run:
                return
            raise ParsingError(f"{context.link} - Included path {include_path} is not an existing file")
        empty_context = Context(path, 0)
        with self._check_include_stack(path, context) as check_passed:
            if not check_passed:
                if self.dry_run:
                    return
                raise ParsingError(f"{context.link} - Cannot process file {path} - circular include")
            yield from self.tokenize(path.read_text(encoding="utf-8"), context=empty_context)

    def _process_stage_direction(self, string: str, kind: NodeKind, context: Context) -> Iterable[Node]:
        """Process inline/block stage direction and iterate nested nodes."""
        for mo in stage_direction_sub_patterns.finditer(string):
            for group, value in mo.groupdict().items():
                if value is None:
                    continue
                if group == "stage_direction":
                    # This can either be an inline_stage_direction or stage_direction (based on passed kind)
                    yield Node(context=context, kind=NodeKind.TEXT, children=[], text=value)
                elif group == "mention":
                    child_nodes: list[Node] = []
                    character: str
                    if (declension_match := declension_sub_pattern.match(value)) is not None:
                        character = declension_match.group("character")
                        declension = declension_match.group("declension")
                        yield Node(
                            context=context,
                            kind=NodeKind.MENTION_WITH_DECLENSION,
                            children=[
                                Node(context=context, kind=NodeKind.MENTION, text=character),
                                Node(context=context, kind=NodeKind.DECLENSION, text=declension),
                            ],
                        )
                    else:
                        character = value
                        yield Node(context=context, kind=NodeKind.MENTION, children=child_nodes, text=character)
                    if character not in self.characters:
                        self.track_violation(
                            f"{context.link} - '{character}' is mentioned but was not properly introduced", context
                        )
                elif group == "declension":
                    # processed within mention
                    continue

    def _process_dialogue(self, dialogue: str, context: Context) -> Iterable[Node]:
        """Process a dialogue article and iterate nested nodes"""
        for mo in dialogue_sub_patterns.finditer(dialogue):
            for group, value in mo.groupdict().items():
                if value is None:
                    continue
                if group == "inline_stage_direction":
                    yield Node(
                        context=context,
                        kind=NodeKind.INLINE_STAGE_DIRECTION,
                        children=list(self._process_stage_direction(value, NodeKind.INLINE_STAGE_DIRECTION, context)),
                    )
                elif group == "dialogue":
                    yield Node(context=context, kind=NodeKind.DIALOGUE, children=[], text=value)

    def _process_speakers(self, speakers: str, context: Context) -> Iterable[Node]:
        """Process a speaker annotation and yield nodes for each speaker"""
        for speaker in speakers.split(","):
            speaker_handle = speaker.strip().lstrip("@")
            if speaker_handle not in self.characters:
                self.track_violation(
                    f"{context.link} - '{speaker_handle}' speaks but was not properly introduced.", context
                )
            yield Node(context=context, kind=NodeKind.SPEAKER, text=speaker_handle)

    def _update_metadata(self, key: str, value: str, context: Context) -> None:
        if key in self.metadata:
            original_context = self.metadata[key].context
            self.track_violation(
                f"{context.link} - Metadata key '{key}' was previously set in {original_context.link}", context
            )
        self.metadata[key] = Metadata(key=key, value=value, context=context)

    def _call_function(self, function_name: str, arguments_string: str, context: Context) -> None | Iterable[Node]:
        if function_name not in self._functions:
            self.track_violation(
                f"Called to undefined function '{function_name}'",
                context,
                LintingViolationSeverity.ERROR,
                log=self.dry_run,
            )
            if self.dry_run:
                return None
            raise ParsingError(f"Called to undefined function '{function_name}' at {context.link}")
        handler = self._functions[function_name]
        arguments = map(str.strip, arguments_string.split(";"))
        return handler(*arguments, context=context)

    @staticmethod
    def parse(path: Path | str, *, dry_run: bool = False) -> StageScript:
        tokenizer = Tokenizer(dry_run=dry_run)
        path = Path(path)
        root_context = Context(path=path, lineno=0)
        nodes = list(tokenizer.tokenize(path.read_text(encoding="utf-8"), context=root_context))
        return StageScript(
            name=tokenizer.play_name,
            metadata=tokenizer.metadata,
            characters=tokenizer.characters,
            nodes=nodes,
            violations=tokenizer.violations,
        )

    def _process_node(self, group: str, value: str, context: Context) -> Iterable[Node]:
        match group:
            case "dialogue":
                children = self._process_dialogue(dialogue=value, context=context)
                yield Node(context=context, kind=NodeKind.DIALOGUE, children=list(children))
            case "play_name":
                if self.play_name is not None:
                    self.track_violation(f"Play already had a name '{self.play_name}'", context)
                self.play_name = value
            case "act_name":
                yield Node(
                    context=context, kind=NodeKind.ACT, children=[Node(context=context, kind=NodeKind.TEXT, text=value)]
                )
            case "scene_name":
                yield Node(
                    context=context,
                    kind=NodeKind.SCENE,
                    children=[Node(context=context, kind=NodeKind.TEXT, text=value)],
                )
            case "stage_direction":
                children = self._process_stage_direction(value, kind=NodeKind.STAGE_DIRECTION, context=context)
                yield Node(context=context, kind=NodeKind.STAGE_DIRECTION, children=list(children))
            case "speaker":
                yield Node(
                    context=context,
                    kind=NodeKind.SPEAKER,
                    children=list(self._process_speakers(value.strip(), context=context)),
                )
            case default:  # pragma: no cover
                self.track_violation(
                    f"Unexpected token type '{default}' - this is probably an error in the parser itself",
                    context,
                    LintingViolationSeverity.ERROR,
                    log=self.dry_run,
                )
                if not self.dry_run:
                    raise ValueError(f"Unexpected group {default}")

    def tokenize(self, string: str, context: Context) -> Iterable[Node]:
        for mo in self.pattern_toplevel.finditer(string):
            lineno = string.count("\n", 0, mo.span()[0]) + 1
            match_context = Context(path=context.path, lineno=lineno)
            groups = mo.groupdict()
            if (metadata_key := groups.pop("key")) is not None:
                metadata_value = groups.pop("value")
                self._update_metadata(metadata_key, metadata_value, match_context)
                continue
            if (function_name := groups.pop("function")) is not None:
                arguments = groups.pop("function_arguments")
                retval = self._call_function(function_name, arguments, context=match_context)
                if inspect.isgenerator(retval):
                    yield from retval
                continue
            for group, value in groups.items():
                if value is None:
                    continue
                processed_nodes = list(self._process_node(group, value, match_context))
                if not processed_nodes:
                    continue

                if processed_nodes[0].kind == NodeKind.SCENE:
                    self._current_scene = processed_nodes[0]
                    if self._current_act is not None:
                        self._current_act.children.append(self._current_scene)
                    else:
                        yield self._current_scene
                    continue
                elif processed_nodes[0].kind == NodeKind.ACT:
                    self._current_act = processed_nodes[0]
                    yield self._current_act
                    continue

                if self._current_scene is not None:
                    self._current_scene.children.extend(processed_nodes)
                elif self._current_act is not None:
                    self._current_act.children.extend(processed_nodes)
                else:
                    yield from processed_nodes
