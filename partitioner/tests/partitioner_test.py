import logging

import pytest
import requests_mock
from _pytest.logging import LogCaptureFixture
from loguru import logger

from partitioner.index import handler, split


class TestPartitioner:
    @pytest.fixture(scope="function")
    def mocked_env(self, request, monkeypatch):
        for k, v in request.param.items():
            monkeypatch.setenv(k, v)

    @pytest.fixture
    def caplog(self, caplog: LogCaptureFixture):
        logger.add(
            caplog.handler,
            format="{message}",
            level=0,
            filter=lambda record: record["level"].no >= logging.INFO,
            enqueue=False,
        )
        yield caplog

    @requests_mock.Mocker(kw="mock")
    @pytest.mark.parametrize(
        "mocked_env,event,resp_headers,expected,err_log",
        [
            (
                {"LOGGER_LEVEL": "INFO"},
                {"URL": "https://download.test/file_name.zip", "Bucket": "bucket_name", "SingleTaskSize": 10},
                {"Accept-Ranges": "bytes", "Content-Length": "100"},
                {
                    "URL": "https://download.test/file_name.zip",
                    "Bucket": "bucket_name",
                    "Key": "file_name.zip",
                    "Tasks": [
                        {"index": 1, "start": 0, "end": 10},
                        {"index": 2, "start": 11, "end": 21},
                        {"index": 3, "start": 22, "end": 32},
                        {"index": 4, "start": 33, "end": 43},
                        {"index": 5, "start": 44, "end": 54},
                        {"index": 6, "start": 55, "end": 65},
                        {"index": 7, "start": 66, "end": 76},
                        {"index": 8, "start": 77, "end": 87},
                        {"index": 9, "start": 88, "end": 98},
                        {"index": 10, "start": 99, "end": 100},
                    ],
                },
                "",
            ),
            (
                {"LOGGER_LEVEL": "INFO"},
                {"URL": "https://download.test/file_name.zip", "Bucket": "bucket_name", "SingleTaskSize": 10},
                {"Content-Length": "100"},
                {"Error": "accept-range is not supported"},
                "accept-range is not supported",
            ),
        ],
        indirect=["mocked_env"],
    )
    def test_handler(self, caplog, mocked_env, event, resp_headers, expected, err_log, **kwargs):
        kwargs["mock"].head(event.get("URL"), headers=resp_headers)
        assert handler(event, {}) == expected
        assert err_log in caplog.text

    @pytest.mark.parametrize(
        "total,size,expected",
        [
            (0, 3, []),
            (2, 3, [(0, 2)]),
            (3, 2, [(0, 2), (3, 3)]),
            (11, 3, [(0, 3), (4, 7), (8, 11)]),
        ],
    )
    def test_split(self, total: int, size: int, expected: list[(int, int)]) -> None:
        assert expected == split(total, size)
