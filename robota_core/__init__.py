import pathlib

import sys

from loguru import logger


class RemoteProviderError(Exception):
    """The error raised when there is a problem with data from a remote provider."""


def set_up_logger():
    log_path = pathlib.Path("robota.log")
    try:
        log_path.unlink()
    except FileNotFoundError:
        pass

    # remove the default sink before adding new ones
    logger.remove()
    logger.add(sys.stderr, format="{level} - {message}", level="SUCCESS")
    logger.add("robota.log", format="{time:YYYY-MM-DD HH:mm:ss}: {level} - {message}",
               level="DEBUG", delay=True)


set_up_logger()
