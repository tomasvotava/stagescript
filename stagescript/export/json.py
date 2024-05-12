import json
from pathlib import Path

from .base import Exporter


class JSONExporter(Exporter):
    def export(self, path: Path | str) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        with (path / f"{self.file_basename}.json").open("w", encoding="utf-8") as file:
            json.dump(self.script.to_dict(), file, default=str)
