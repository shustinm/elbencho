"""Tests for --s3contentmd5 flag (Content-MD5 header on uploads)."""

import pytest

from helpers.s3_utils import list_all_objects, random_prefix


class TestContentMd5:
    def test_single_part_upload(self, elbencho, s3_client, bucket):
        """Single-part PutObject with Content-MD5 succeeds and objects land in S3."""
        prefix = random_prefix()
        result = elbencho.write_objects(
            [bucket], files=3, size="4k", block="4k",
            extra_args=["--s3objprefix", prefix, "--s3contentmd5"],
        )
        assert result.succeeded
        objects = list_all_objects(s3_client, bucket, prefix=prefix)
        assert len(objects) == 3

    def test_multipart_upload(self, elbencho, s3_client, bucket):
        """Multipart upload with Content-MD5 on each part succeeds."""
        prefix = random_prefix()
        result = elbencho.write_objects(
            [bucket], files=1, size="12m", block="5m",
            extra_args=[
                "--s3objprefix", prefix,
                "--s3contentmd5",
                "--s3mpusplit", "5m",
            ],
            timeout=300,
        )
        assert result.succeeded
        objects = list_all_objects(s3_client, bucket, prefix=prefix)
        assert len(objects) == 1

    def test_combined_with_verify(self, elbencho, bucket):
        """Content-MD5 combined with --verify data integrity check."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=2, size="64k", block="64k",
            extra_args=["--s3objprefix", prefix, "--s3contentmd5", "--verify", "42"],
        )
        result = elbencho.read_objects(
            [bucket], files=2, size="64k", block="64k",
            extra_args=["--s3objprefix", prefix, "--verify", "42"],
        )
        assert result.succeeded

    def test_multiple_threads(self, elbencho, s3_client, bucket):
        """Content-MD5 works correctly across multiple threads."""
        prefix = random_prefix()
        result = elbencho.write_objects(
            [bucket], threads=2, files=4, size="4k", block="4k",
            extra_args=["--s3objprefix", prefix, "--s3contentmd5"],
        )
        assert result.succeeded
        objects = list_all_objects(s3_client, bucket, prefix=prefix)
        assert len(objects) == 4 * 2
