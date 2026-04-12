"""Tests for data integrity verification (--verify flag)."""

import pytest

from helpers.elbencho import ElbenchoError
from helpers.s3_utils import random_prefix


class TestDataIntegrity:
    def test_verify_single_object(self, elbencho, bucket):
        """Write with --verify salt, read back with same salt -> success."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=1, size="64k", block="64k",
            extra_args=["--s3objprefix", prefix, "--verify", "42"],
        )
        result = elbencho.read_objects(
            [bucket], files=1, size="64k", block="64k",
            extra_args=["--s3objprefix", prefix, "--verify", "42"],
        )
        assert result.succeeded

    def test_verify_multiple_objects(self, elbencho, bucket):
        """Verify across multiple objects and threads."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], threads=2, dirs=1, files=4, size="32k", block="32k",
            extra_args=["--s3objprefix", prefix, "--verify", "7"],
        )
        result = elbencho.read_objects(
            [bucket], threads=2, dirs=1, files=4, size="32k", block="32k",
            extra_args=["--s3objprefix", prefix, "--verify", "7"],
        )
        assert result.succeeded

    def test_verify_wrong_salt_fails(self, elbencho, bucket):
        """Write with salt 1, read-verify with salt 2 -> should fail."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=1, size="64k", block="64k",
            extra_args=["--s3objprefix", prefix, "--verify", "1"],
        )
        with pytest.raises(ElbenchoError):
            elbencho.read_objects(
                [bucket], files=1, size="64k", block="64k",
                extra_args=["--s3objprefix", prefix, "--verify", "2"],
            )

    def test_verify_medium_object(self, elbencho, bucket):
        """Integrity check on a medium-sized object payload."""
        prefix = random_prefix()
        elbencho.write_objects(
            [bucket], files=1, size="4m", block="4m",
            extra_args=["--s3objprefix", prefix, "--verify", "99"],
            timeout=300,
        )
        result = elbencho.read_objects(
            [bucket], files=1, size="4m", block="4m",
            extra_args=["--s3objprefix", prefix, "--verify", "99"],
            timeout=300,
        )
        assert result.succeeded
