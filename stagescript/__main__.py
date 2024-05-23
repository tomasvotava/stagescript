import logging
from pathlib import Path
from typing import Any

import click

from stagescript import JSONExporter, MarkdownExporter, ODFTextExporter
from stagescript.export.base import Exporter
from stagescript.log import get_logger

from . import Tokenizer

logger = get_logger(__name__)

exporter_classes: dict[str, type[Exporter]] = {
    "markdown": MarkdownExporter,
    "json": JSONExporter,
    "odftext": ODFTextExporter,
}


class CatchAllCommand(click.Command):
    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except Exception as error:
            if ctx.obj and ctx.obj.get("loglevel") == "DEBUG":
                raise
            logger.error(str(error))
            ctx.exit(1)


@click.group()
@click.option(
    "--level",
    type=click.Choice(("DEBUG", "INFO", "WARNING", "ERROR")),
    default="INFO",
    help="Set loglevel for parsing and linting output",
)
@click.pass_context
def cli(ctx: click.Context, level: str) -> None:
    ctx.obj = {"loglevel": level}
    logging.getLogger().setLevel(level)


@cli.command("lint", cls=CatchAllCommand)
@click.argument("files", nargs=-1, type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True))
def lint(files: tuple[str]) -> None:
    if not files:
        raise ValueError("No files were passed")
    for file in files:
        Tokenizer.parse(file, dry_run=True)


@cli.command("convert", cls=CatchAllCommand)
@click.argument("file", type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option("--output", "-o", type=click.Path(file_okay=False, dir_okay=True, writable=True), default="./output")
@click.option("--type", "-t", "type_", type=click.Choice(list(exporter_classes.keys())), default="markdown")
def convert(file: str, output: str, type_: str) -> None:
    script = Tokenizer.parse(file)
    if type_ not in exporter_classes:
        raise ValueError(f"{type_!r} is an unknown output type")
    ExporterClass = exporter_classes[type_]  # noqa: N806
    exporter = ExporterClass(script)
    exporter.export(Path(output))


if __name__ == "__main__":
    cli()
