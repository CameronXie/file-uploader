import logging
import os
from http import HTTPStatus
from os import remove
from os.path import join
from tempfile import gettempdir
from unittest.mock import patch

import boto3
import pytest
import requests_mock
from _pytest.logging import LogCaptureFixture
from loguru import logger
from moto import mock_s3

from uploader.index import download_file, handler


class TestUploader:
    @pytest.fixture(scope="function")
    def mocked_env(self, request, monkeypatch):
        for k, v in request.param.items():
            monkeypatch.setenv(k, v)

    @pytest.fixture(scope="function")
    def caplog(self, caplog: LogCaptureFixture):
        logger.add(
            caplog.handler,
            format="{message}",
            level=0,
            filter=lambda record: record["level"].no >= logging.INFO,
            enqueue=False,
        )
        yield caplog

    @pytest.fixture(scope="function")
    def mocked_boto3_resource(self):
        with patch("boto3.resource", autospec=True) as m:
            yield m

    @mock_s3
    @pytest.mark.parametrize("mocked_env", [{"LOGGER_LEVEL": "INFO"}], indirect=True)
    def test_handler(self, requests_mock, caplog, mocked_env):
        event = {
            "URL": "https://download.test/file_name.txt",
            "Bucket": "bucket_name",
            "Key": "file_name.txt",
            "Task": {"index": 1, "start": 0, "end": 10},
        }
        download_file_content = "download_content"
        requests_mock.get(event.get("URL"), text=download_file_content, status_code=HTTPStatus.PARTIAL_CONTENT)

        s3_resource = boto3.resource("s3", region_name=os.getenv("AWS_DEFAULT_REGION"))
        s3_client = boto3.client("s3")
        s3_resource.create_bucket(Bucket=event.get("Bucket"))

        multipart_resp = s3_client.create_multipart_upload(Bucket=event.get("Bucket"), Key=event.get("Key"))
        event["MultipartUploadId"] = multipart_resp["UploadId"]
        result = handler(event, {})

        uploaded_parts = s3_client.list_parts(
            Bucket=event.get("Bucket"), Key=event.get("Key"), UploadId=multipart_resp["UploadId"]
        )["Parts"]

        assert len(uploaded_parts) == 1

        uploaded_part = uploaded_parts[0]
        assert len(download_file_content) == uploaded_part["Size"]
        assert result == {"ETag": uploaded_part["ETag"], "PartNumber": 1}

    @requests_mock.Mocker(kw="mock")
    @pytest.mark.parametrize(
        "start,end,status_code,err_msg",
        [
            (0, 10, HTTPStatus.PARTIAL_CONTENT, None),
            (20, 10, HTTPStatus.PARTIAL_CONTENT, "start value 20 is not less then end value 10"),
            (0, 10, HTTPStatus.OK, "download failed, received status code 200"),
        ],
    )
    def test_download_file(self, start, end, status_code, err_msg, **kwargs) -> None:
        m = kwargs["mock"]
        url = "https://download.test/file_name.txt"
        download_content = "download_test_content"
        m.get(url, text=download_content, status_code=status_code)

        if err_msg is not None:
            with pytest.raises(ValueError, match=err_msg):
                download_file("https://download.test/file_name.txt", start, end)

            return

        file_name = download_file("https://download.test/file_name.txt", start, end)

        assert file_name == join(gettempdir(), "file_name.txt")
        assert m.last_request.headers.get("Range") == f"bytes={start}-{end}"
        with open(file_name, "r") as f:
            assert f.read() == download_content

        remove(file_name)
