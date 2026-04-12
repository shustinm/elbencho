"""Tests for S3 object and bucket tagging."""

from helpers.s3_utils import random_prefix


class TestObjectTagging:
    def test_object_tag_and_verify(self, elbencho, bucket):
        """Write objects with tagging enabled, then verify tags via elbencho."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=2, size="4k", block="4k",
            extra_args=["--s3objprefix", prefix, "--s3otag"],
        )

        result = elbencho.run(
            [
                "--s3otag", "--s3otagverify",
                "-r", "-n", "0",
                "-N", "2", "-s", "4k", "-b", "4k",
                "--s3objprefix", prefix,
                "--no0usecerr",
            ],
            buckets=[bucket],
        )
        assert result.succeeded


class TestBucketTagging:
    def test_bucket_tag_and_verify(self, elbencho, bucket):
        """Set bucket tags and verify them.

        PutBucketTagging is tied to the create-dirs phase: ``getRunS3PutBucketMetadata()``
        requires ``-d`` (see Coordinator / ProgArgs). Without ``-d``, only GET runs and no
        tags are written.
        """
        result = elbencho.run(
            ["-d", "--s3btag", "--s3btagverify", "--no0usecerr"],
            buckets=[bucket],
        )
        assert result.succeeded
