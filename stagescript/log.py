import logging

import colorlog


def get_logger(name: str | None = None) -> logging.Logger:
    logger = colorlog.getLogger(name)
    color_handler = colorlog.StreamHandler()
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s[%(levelname)-8s] %(message)s", log_colors=colorlog.default_log_colors | {"DEBUG": "light_black"}
    )
    color_handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(color_handler)
    logger.propagate = False
    return logger
