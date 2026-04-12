"""Tests for S3 ACL operations (object and bucket)."""

from helpers.s3_utils import random_prefix


class TestBucketACL:
    def test_get_bucket_acl(self, elbencho, bucket):
        result = elbencho.run(
            ["--s3baclget", "--no0usecerr"],
            buckets=[bucket],
        )
        assert result.succeeded


class TestObjectACL:
    def test_get_object_acl(self, elbencho, bucket):
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=1, size="4k", block="4k",
            extra_args=["--s3objprefix", prefix],
        )

        result = elbencho.run(
            [
                "--s3aclget",
                "-n", "0",
                "-N", "1", "-s", "4k", "-b", "4k",
                "--s3objprefix", prefix,
                "--no0usecerr",
            ],
            buckets=[bucket],
        )
        assert result.succeeded
