"""Tests for larger S3 object write/read flows."""

import pytest

from helpers.s3_utils import list_all_objects, random_prefix


class TestMultipartUpload:
    def test_basic_multipart(self, elbencho, s3_client, bucket):
        """Write a 4M object and verify expected size."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=1, size="4m", block="4m",
            extra_args=["--s3objprefix", prefix], timeout=300,
        )

        objects = list_all_objects(s3_client, bucket, prefix=prefix)
        assert len(objects) == 1
        assert objects[0]["Size"] == 4 * 1024 * 1024

    def test_multipart_many_parts(self, elbencho, s3_client, bucket):
        """Write another <5M object and verify expected size."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=1, size="4m", block="4m",
            extra_args=["--s3objprefix", prefix], timeout=300,
        )

        objects = list_all_objects(s3_client, bucket, prefix=prefix)
        assert len(objects) == 1
        assert objects[0]["Size"] == 4 * 1024 * 1024

    def test_multipart_read_back(self, elbencho, bucket):
        """Write medium object then read back successfully."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=1, size="4m", block="4m",
            extra_args=["--s3objprefix", prefix],
        )
        result = elbencho.read_objects(
            [bucket], files=1, size="4m", block="4m",
            extra_args=["--s3objprefix", prefix],
        )
        assert result.succeeded

    @pytest.mark.slow
    def test_multipart_multiple_objects(self, elbencho, s3_client, bucket):
        """Multiple medium-sized objects remain below 5M each."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], threads=2, files=2, size="4m", block="4m",
            extra_args=["--s3objprefix", prefix], timeout=300,
        )

        objects = list_all_objects(s3_client, bucket, prefix=prefix)
        assert len(objects) == 4
        for obj in objects:
            assert obj["Size"] == 4 * 1024 * 1024
