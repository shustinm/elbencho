"""Tests for S3 bucket create, stat, and delete operations."""


class TestBucketCreate:
    def test_create_already_existing_bucket(self, elbencho, bucket):
        result = elbencho.create_buckets([bucket])
        assert result.succeeded


class TestBucketStat:
    def test_stat_existing_bucket(self, elbencho, bucket):
        result = elbencho.stat_buckets([bucket])
        assert result.succeeded

