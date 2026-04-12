"""Tests for S3 CopyObject via --s3copyobj."""

import pytest
from helpers.elbencho import ElbenchoError
from helpers.s3_utils import list_all_objects, random_prefix


class TestObjectCopy:
    def test_copy_within_same_bucket_using_prefix(self, elbencho, s3_client, bucket):
        """Objects are copied within one bucket from one prefix to another."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=3, size="4k", block="4k",
            extra_args=["--s3objprefix", f"{prefix}src/"],
        )

        result = elbencho.copy_objects(
            [bucket], files=3, size="4k", block="4k",
            src_prefix=f"{prefix}src/", dst_prefix=f"{prefix}dst/",
        )
        assert result.succeeded

        src_objects = list_all_objects(s3_client, bucket, prefix=f"{prefix}src/")
        dst_objects = list_all_objects(s3_client, bucket, prefix=f"{prefix}dst/")
        assert len(src_objects) == 3
        assert len(dst_objects) == 3

    def test_copy_cross_bucket(self, elbencho, s3_client, bucket, locked_bucket):
        """Objects are copied from one bucket to a different bucket."""
        src_bucket, dst_bucket = bucket, locked_bucket
        prefix = random_prefix()

        elbencho.write_objects(
            [src_bucket], files=2, size="8k", block="8k",
            extra_args=["--s3objprefix", prefix],
        )

        result = elbencho.copy_objects(
            [dst_bucket], files=2, size="8k", block="8k",
            src_bucket=src_bucket,
            src_prefix=prefix, dst_prefix=prefix,
        )
        assert result.succeeded

        src_objects = list_all_objects(s3_client, src_bucket, prefix=prefix)
        dst_objects = list_all_objects(s3_client, dst_bucket, prefix=prefix)
        assert len(src_objects) == 2
        assert len(dst_objects) == 2
        for obj in dst_objects:
            assert obj["Size"] == 8 * 1024

    def test_copy_preserves_object_size(self, elbencho, s3_client, bucket):
        """Copied objects retain the original size."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=1, size="16k", block="16k",
            extra_args=["--s3objprefix", f"{prefix}orig/"],
        )

        elbencho.copy_objects(
            [bucket], files=1, size="16k", block="16k",
            src_prefix=f"{prefix}orig/", dst_prefix=f"{prefix}copy/",
        )

        copied = list_all_objects(s3_client, bucket, prefix=f"{prefix}copy/")
        assert len(copied) == 1
        assert copied[0]["Size"] == 16 * 1024

    def test_copy_cross_bucket_with_prefix(self, elbencho, s3_client, bucket, locked_bucket):
        """Cross-bucket copy with independent source and destination prefixes."""
        src_bucket, dst_bucket = bucket, locked_bucket
        prefix = random_prefix()

        elbencho.write_objects(
            [src_bucket], files=2, size="4k", block="4k",
            extra_args=["--s3objprefix", f"{prefix}alpha/"],
        )

        result = elbencho.copy_objects(
            [dst_bucket], files=2, size="4k", block="4k",
            src_bucket=src_bucket,
            src_prefix=f"{prefix}alpha/", dst_prefix=f"{prefix}beta/",
        )
        assert result.succeeded

        dst_objects = list_all_objects(s3_client, dst_bucket, prefix=f"{prefix}beta/")
        assert len(dst_objects) == 2

    def test_copy_multiple_threads(self, elbencho, s3_client, bucket):
        """Copy works correctly with multiple threads and dirs."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], threads=2, dirs=1, files=4, size="4k", block="4k",
            extra_args=["--s3objprefix", f"{prefix}src/"],
        )

        result = elbencho.copy_objects(
            [bucket], threads=2, dirs=1, files=4, size="4k", block="4k",
            src_prefix=f"{prefix}src/", dst_prefix=f"{prefix}dst/",
        )
        assert result.succeeded

        dst_objects = list_all_objects(s3_client, bucket, prefix=f"{prefix}dst/")
        assert len(dst_objects) == 2 * 1 * 4

    def test_copy_without_required_flag_fails(self, elbencho, bucket):
        """--s3copybucket without --s3copyobj is rejected."""
        with pytest.raises(ElbenchoError):
            elbencho.run(
                ["--s3copybucket", bucket, "--no0usecerr", "-N", "1", "-s", "4k", "-b", "4k"],
                buckets=[bucket],
            )

    def test_copy_src_prefix_without_copyobj_fails(self, elbencho, bucket):
        """--s3copysrcpfx without --s3copyobj is rejected."""
        with pytest.raises(ElbenchoError):
            elbencho.run(
                ["--s3copysrcpfx", "pfx/", "--no0usecerr", "-N", "1", "-s", "4k", "-b", "4k"],
                buckets=[bucket],
            )


