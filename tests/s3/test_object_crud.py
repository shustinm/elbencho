"""Tests for S3 object write, read, and delete operations."""

from helpers.s3_utils import list_all_objects, random_prefix


class TestObjectWrite:
    def test_single_object_write(self, elbencho, s3_client, bucket):
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=1, size="64k", block="64k",
            extra_args=["--s3objprefix", prefix],
        )

        objects = list_all_objects(s3_client, bucket, prefix=prefix)
        assert len(objects) == 1
        assert objects[0]["Size"] == 64 * 1024

    def test_multiple_objects_write(self, elbencho, s3_client, bucket):
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], threads=2, dirs=1, files=4, size="32k", block="32k",
            extra_args=["--s3objprefix", prefix],
        )

        objects = list_all_objects(s3_client, bucket, prefix=prefix)
        assert len(objects) == 2 * 1 * 4  # threads * dirs * files

    def test_write_with_prefix(self, elbencho, s3_client, bucket):
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=2, size="16k", block="16k",
            extra_args=["--s3objprefix", f"{prefix}myprefix/"],
        )

        objects = list_all_objects(s3_client, bucket, prefix=f"{prefix}myprefix/")
        assert len(objects) == 2


class TestObjectRead:
    def test_write_then_read(self, elbencho, bucket):
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=3, size="64k", block="64k",
            extra_args=["--s3objprefix", prefix],
        )
        result = elbencho.read_objects(
            [bucket], files=3, size="64k", block="64k",
            extra_args=["--s3objprefix", prefix],
        )
        assert result.succeeded

    def test_read_with_multiple_threads(self, elbencho, bucket):
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], threads=2, dirs=1, files=4, size="32k", block="32k",
            extra_args=["--s3objprefix", prefix],
        )
        result = elbencho.read_objects(
            [bucket], threads=2, dirs=1, files=4, size="32k", block="32k",
            extra_args=["--s3objprefix", prefix],
        )
        assert result.succeeded


class TestObjectDelete:
    def test_delete_objects(self, elbencho, s3_client, bucket):
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], threads=2, dirs=1, files=4, size="16k", block="16k",
            extra_args=["--s3objprefix", prefix],
        )
        assert len(list_all_objects(s3_client, bucket, prefix=prefix)) == 8

        elbencho.delete_objects(
            [bucket], threads=2, dirs=1, files=4,
            extra_args=["--s3objprefix", prefix],
        )
        assert len(list_all_objects(s3_client, bucket, prefix=prefix)) == 0

    def test_multidel(self, elbencho, s3_client, bucket):
        """Test bulk delete via --s3multidel."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=10, size="4k", block="4k",
            extra_args=["--s3objprefix", prefix],
        )
        assert len(list_all_objects(s3_client, bucket, prefix=prefix)) == 10

        elbencho.run(
            ["--s3multidel", "1000", "--s3objprefix", prefix, "--no0usecerr"],
            buckets=[bucket],
        )
        assert len(list_all_objects(s3_client, bucket, prefix=prefix)) == 0


class TestObjectOverwrite:
    def test_overwrite_same_key(self, elbencho, s3_client, bucket):
        """Writing the same key twice should update the object."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=1, size="32k", block="32k",
            extra_args=["--s3objprefix", prefix],
        )
        elbencho.write_objects(
            [bucket], files=1, size="64k", block="64k",
            extra_args=["--s3objprefix", prefix],
        )

        objects = list_all_objects(s3_client, bucket, prefix=prefix)
        assert len(objects) == 1
        assert objects[0]["Size"] == 64 * 1024
