import logging
from http import HTTPStatus
from os import getenv
from os.path import basename, join
from shutil import copyfileobj
from sys import stdout
from tempfile import gettempdir
from typing import Optional, Union

from boto3 import resource
from loguru import logger
from requests import get


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


def download_file(url: str, start: int, end: int) -> str:
    if start > end:
        raise ValueError(f"range start value {start} is not less then end value {end}")

    file_name = join(gettempdir(), basename(url))

    with get(url, headers={"Range": f"bytes={start}-{end}"}, stream=True) as r:
        if r.status_code != HTTPStatus.PARTIAL_CONTENT:
            raise ValueError(f"download failed, received status code {r.status_code}")

        with open(file_name, "wb") as f:
            copyfileobj(r.raw, f)

    return file_name


def get_completed_part(etag: str, part_num: int) -> dict:
    return {"ETag": etag, "PartNumber": part_num}


def handler(event, context):
    Logger.init(getenv("LOGGER_LEVEL"))
    logger.debug(event)
    task = event.get("Task")
    task_num = task.get("index")

    file = download_file(event.get("URL"), task.get("start"), task.get("end"))
    with open(file, "rb") as f:
        resp = (
            resource("s3")
            .MultipartUploadPart(
                event.get("Bucket"),
                event.get("Key"),
                event.get("MultipartUploadId"),
                task_num,
            )
            .upload(Body=f)
        )

        logger.debug(resp)

    return get_completed_part(resp.get("ETag"), task_num)
