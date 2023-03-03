import logging
from math import ceil
from os import getenv
from os.path import basename
from sys import stdout
from typing import Optional, Union

from loguru import logger
from requests import head


class Logger:
    is_initialized = False

    @staticmethod
    def init(level: Optional[Union[int, str]]) -> None:
        if Logger.is_initialized is True:
            return

        logger.remove()
        logger_level = level if level is not None else logging.DEBUG
        logger.add(stdout, level=logger_level)
        Logger.is_initialized = True


def get_file_name(url: str) -> str:
    return basename(url)


def get_file_size(url: str) -> int:
    resp = head(url)
    headers = resp.headers

    if headers.get("Accept-Ranges") != "bytes":
        raise ValueError("accept-range is not supported")

    size = headers.get("Content-Length")
    if size is None:
        raise ValueError("content-length is not found in response header")

    return int(size)


def split(total: int, size: int) -> list[(int, int)]:
    result = []
    for i in range(ceil(total / size)):
        start = (size + min(1, i)) * i
        end = min(start + size, total)
        result.append((start, end))

        if end == total:
            break

    return result


def get_tasks(tasks: list[(int, int)]) -> list[dict]:
    return [{"index": idx + 1, "start": start, "end": end} for idx, (start, end) in enumerate(tasks)]


def get_error(msg: str) -> dict:
    return {"Error": msg}


def handler(event, context):
    Logger.init(getenv("LOGGER_LEVEL"))
    logger.debug(event)
    download_url = event.get("URL")

    try:
        return {
            "URL": download_url,
            "Bucket": event.get("Bucket"),
            "Key": get_file_name(download_url),
            "Tasks": get_tasks(split(get_file_size(download_url), event.get("SingleTaskSize"))),
        }
    except ValueError as e:
        logger.error(e)
        return get_error(str(e))
