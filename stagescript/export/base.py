from abc import ABC, abstractmethod
from pathlib import Path

from slugify import slugify

from stagescript.entities import StageScript
from stagescript.log import get_logger
from stagescript.naming import get_random_slug

logger = get_logger(__name__)


class Exporter(ABC):
    def __init__(self, script: StageScript) -> None:
        self.script = script
        if script.name is None:
            self.file_basename = get_random_slug()
            logger.warning("The play being exported has no name, using generated name: %s", self.file_basename)
        else:
            self.file_basename = slugify(script.name)

    def get_character_name(self, handle: str) -> str:
        """Returns either the character's name or the handle if the character was not introduced"""
        if handle not in self.script.characters:
            return handle
        return self.script.characters[handle].name

    @abstractmethod
    def export(self, path: Path | str) -> None:
        pass
