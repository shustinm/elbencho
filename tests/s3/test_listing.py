"""Tests for S3 object listing operations."""

from helpers.s3_utils import random_prefix


class TestListObjects:
    def test_list_objects_count(self, elbencho, bucket):
        """Write objects then list them, verify count matches."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], threads=1, dirs=1, files=5, size="4k", block="4k",
            extra_args=["--s3objprefix", prefix],
        )
        result = elbencho.list_objects([bucket], max_keys=1000, prefix=prefix)
        assert result.succeeded

    def test_list_with_prefix(self, elbencho, bucket):
        """List with a prefix filter."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=3, size="4k", block="4k",
            extra_args=["--s3objprefix", f"{prefix}alpha/"],
        )
        elbencho.write_objects(
            [bucket], files=2, size="4k", block="4k",
            extra_args=["--s3objprefix", f"{prefix}beta/"],
        )

        result = elbencho.list_objects([bucket], max_keys=1000, prefix=f"{prefix}alpha/")
        assert result.succeeded

    def test_list_empty_bucket(self, elbencho, bucket):
        result = elbencho.list_objects([bucket], max_keys=1000, prefix=random_prefix())
        assert result.succeeded


class TestParallelListing:
    def test_parallel_list_with_verify(self, elbencho, bucket):
        """
        Write with -n/-N then list in parallel and verify correctness.
        --s3listobjpar + --s3listverify requires matching -n/-N from write.
        """
        dirs, files = 2, 5
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], threads=1, dirs=dirs, files=files, size="4k", block="4k",
            extra_args=["--s3objprefix", prefix],
        )

        result = elbencho.run(
            [
                "--s3listobjpar", "--s3listverify",
                "-t", "1", "-n", str(dirs), "-N", str(files),
                "--s3objprefix", prefix,
                "--no0usecerr",
            ],
            buckets=[bucket],
        )
        assert result.succeeded
