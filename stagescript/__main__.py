import logging
from typing import Any

import click

from stagescript.log import get_logger
from stagescript.parser import StagescriptParser

logger = get_logger(__name__)


class CatchAllCommand(click.Command):
    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except Exception as error:
            logger.error(str(error))
            ctx.exit(1)


@click.group()
@click.option(
    "--level",
    type=click.Choice(("DEBUG", "INFO", "WARNING", "ERROR")),
    default="INFO",
    help="Set loglevel for parsing and linting output",
)
def cli(level: str) -> None:
    logging.getLogger().setLevel(level)


@cli.command("lint", cls=CatchAllCommand)
@click.argument("files", nargs=-1, type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True))
def lint(files: tuple[str]) -> None:
    if not files:
        raise ValueError("No files were passed")
    for file in files:
        parser = StagescriptParser()
        parser.parse(file)


if __name__ == "__main__":
    cli()
