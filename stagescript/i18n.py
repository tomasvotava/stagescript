import gettext
from collections.abc import Callable
from pathlib import Path

from stagescript.log import get_logger

logger = get_logger(__name__)

DEFAULT_LANGUAGE = "en"

localedir = (Path(__file__).parent.parent / "i18n").as_posix()


gettext.bindtextdomain("stagescript", localedir=localedir)
gettext.textdomain("stagescript")


def get_translation(language: str = DEFAULT_LANGUAGE) -> Callable[[str], str]:
    try:
        translation = gettext.translation("stagescript", localedir=localedir, languages=[language])
    except FileNotFoundError:
        logger.warning(f"Failed to load locale for language {language!r}, using default {DEFAULT_LANGUAGE!r}.")
        try:
            translation = gettext.translation("stagescript", localedir=localedir, languages=[DEFAULT_LANGUAGE])
        except FileNotFoundError:
            logger.warning("Failed to load locale for default language, using no translation, this may look bad.")
            return gettext.gettext
    return translation.gettext


__all__ = ["get_translation"]
