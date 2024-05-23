import json
from pathlib import Path

from .base import Exporter


class JSONExporter(Exporter):
    def _export(self, path: Path) -> None:
        with (path / f"{self.file_basename}.json").open("w", encoding="utf-8") as file:
            json.dump(self.script.to_dict(), file, default=str, ensure_ascii=False)
