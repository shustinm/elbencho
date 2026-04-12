"""Tests for S3 object retention, legal hold, and object lock configuration."""

import pytest
from botocore.exceptions import ClientError

from helpers.elbencho import ElbenchoError
from helpers.s3_utils import (
    get_object_legal_hold,
    get_object_retention,
    list_all_objects,
    random_prefix,
)


RETENTION_MINUTES = 1
# Same prefix on two writes so the second run targets the same key (new object version).
_RETAIN_PREFIX = "retlock/"


class TestObjectRetention:
    """Per-object GOVERNANCE retention set via --s3oretention."""

    def test_write_with_retention_and_verify(self, elbencho, locked_bucket):
        """Write applies retention; elbencho runs GetObjectRetention in the same run when verify is on."""
        prefix = random_prefix()
        result = elbencho.write_objects(
            [locked_bucket], files=2, size="4k", block="4k",
            extra_args=[
                "--s3objprefix", prefix,
                "--s3oretention",
                "--s3oretentionminutes", str(RETENTION_MINUTES),
                "--s3oretentionverify",
            ],
        )
        assert result.succeeded

    def test_retention_visible_via_boto3(self, elbencho, s3_client, locked_bucket):
        """Retention set by elbencho is independently visible through the S3 GetObjectRetention API."""
        prefix = random_prefix()
        elbencho.write_objects(
            [locked_bucket], files=1, size="4k", block="4k",
            extra_args=[
                "--s3objprefix", prefix,
                "--s3oretention",
                "--s3oretentionminutes", str(RETENTION_MINUTES),
            ],
        )

        objects = list_all_objects(s3_client, locked_bucket, prefix=prefix)
        assert len(objects) == 1

        retention = get_object_retention(s3_client, locked_bucket, objects[0]["Key"])
        assert retention["Mode"] == "GOVERNANCE"
        assert "RetainUntilDate" in retention

    def test_prior_retained_version_unchanged_after_new_put(
        self, elbencho, s3_client, locked_bucket,
    ):
        """A second elbencho write to the same key does not clear GOVERNANCE on the prior version."""
        prefix = f"{random_prefix()}{_RETAIN_PREFIX}"
        elbencho.write_objects(
            [locked_bucket], files=1, size="4k", block="4k",
            extra_args=[
                "--s3objprefix", prefix,
                "--s3oretention",
                "--s3oretentionminutes", str(RETENTION_MINUTES),
            ],
        )

        objects = list_all_objects(s3_client, locked_bucket, prefix=prefix)
        key = objects[0]["Key"]
        v1 = s3_client.head_object(Bucket=locked_bucket, Key=key)["VersionId"]

        elbencho.write_objects(
            [locked_bucket], files=1, size="4k", block="4k",
            extra_args=["--s3objprefix", prefix],
        )

        retention = get_object_retention(s3_client, locked_bucket, key, version_id=v1)
        assert retention["Mode"] == "GOVERNANCE"
        assert "RetainUntilDate" in retention

    def test_delete_rejected_for_retained_version_id(self, elbencho, s3_client, locked_bucket):
        """DeleteObject must fail for the specific version under retention (VersionId required)."""
        prefix = random_prefix()
        elbencho.write_objects(
            [locked_bucket], files=1, size="4k", block="4k",
            extra_args=[
                "--s3objprefix", prefix,
                "--s3oretention",
                "--s3oretentionminutes", str(RETENTION_MINUTES),
            ],
        )

        objects = list_all_objects(s3_client, locked_bucket, prefix=prefix)
        key = objects[0]["Key"]
        version_id = s3_client.head_object(Bucket=locked_bucket, Key=key)["VersionId"]

        with pytest.raises(ClientError) as exc:
            s3_client.delete_object(
                Bucket=locked_bucket, Key=key, VersionId=version_id,
            )
        r = exc.value.response
        err = r["Error"]["Code"]
        status = r["ResponseMetadata"]["HTTPStatusCode"]
        # S3 may respond with 403 AccessDenied or 400 InvalidRequest for a
        # GOVERNANCE-retained version delete, depending on API path / account.
        assert (err == "AccessDenied" and status == 403) or (
            err == "InvalidRequest" and status == 400
        )

    def test_write_delete_read_retained_object(self, elbencho, s3_client, locked_bucket):
        """Write a retained object, delete (creates delete marker); listing is empty; read fails.

        Delete succeeds (creates a delete marker on a versioned bucket), so the
        object disappears from listing. A normal read then fails (no object visible).
        """
        prefix = random_prefix()

        elbencho.write_objects(
            [locked_bucket], files=1, size="4k", block="4k",
            extra_args=[
                "--s3objprefix", prefix,
                "--s3oretention",
                "--s3oretentionminutes", str(RETENTION_MINUTES),
            ],
        )

        objects = list_all_objects(s3_client, locked_bucket, prefix=prefix)
        assert len(objects) == 1

        delete_result = elbencho.delete_objects(
            [locked_bucket], files=1,
            extra_args=["--s3objprefix", prefix],
        )
        assert delete_result.succeeded

        assert list_all_objects(s3_client, locked_bucket, prefix=prefix) == []

        with pytest.raises(ElbenchoError):
            elbencho.read_objects(
                [locked_bucket], files=1, size="4k", block="4k",
                extra_args=["--s3objprefix", prefix],
            )


class TestObjectLockConfiguration:
    """Bucket-level lock configuration via --s3olockcfg.

    Uses lock_config_bucket (a dedicated bucket) so the 1-day GOVERNANCE
    default retention rule it sets does not affect other test classes.
    """

    def test_put_and_verify_lock_config(self, elbencho, lock_config_bucket):
        """Setting and verifying object lock configuration on a lock-enabled bucket succeeds."""
        result = elbencho.run(
            ["-d", "--s3olockcfg", "--s3olockcfgverify", "--no0usecerr"],
            buckets=[lock_config_bucket],
        )
        assert result.succeeded


class TestObjectLegalHold:
    """Per-object legal hold set/removed via --s3olegalhold."""

    def test_default_status_is_on(self, elbencho, s3_client, locked_bucket):
        """--s3olegalhold without --s3olegalholdstatus defaults to ON."""
        prefix = random_prefix()
        elbencho.write_objects(
            [locked_bucket], files=1, size="4k", block="4k",
            extra_args=["--s3objprefix", prefix, "--s3olegalhold"],
        )

        objects = list_all_objects(s3_client, locked_bucket, prefix=prefix)
        assert len(objects) == 1
        status = get_object_legal_hold(s3_client, locked_bucket, objects[0]["Key"])
        assert status == "ON"

    def test_put_legal_hold_on_and_verify(self, elbencho, locked_bucket):
        """Write phase sets legal hold ON and elbencho verifies the status in the same run."""
        prefix = random_prefix()
        result = elbencho.write_objects(
            [locked_bucket], files=2, size="4k", block="4k",
            extra_args=[
                "--s3objprefix", prefix,
                "--s3olegalhold",
                "--s3olegalholdstatus", "ON",
                "--s3olegatholdrverify",
            ],
        )
        assert result.succeeded

    def test_put_legal_hold_off_and_verify(self, elbencho, locked_bucket):
        """Write phase sets legal hold OFF and elbencho verifies the status in the same run."""
        prefix = random_prefix()
        result = elbencho.write_objects(
            [locked_bucket], files=2, size="4k", block="4k",
            extra_args=[
                "--s3objprefix", prefix,
                "--s3olegalhold",
                "--s3olegalholdstatus", "OFF",
                "--s3olegatholdrverify",
            ],
        )
        assert result.succeeded

    def test_legal_hold_on_visible_via_boto3(self, elbencho, s3_client, locked_bucket):
        """Legal hold ON set by elbencho is independently visible through the S3 API."""
        prefix = random_prefix()
        elbencho.write_objects(
            [locked_bucket], files=1, size="4k", block="4k",
            extra_args=[
                "--s3objprefix", prefix,
                "--s3olegalhold",
                "--s3olegalholdstatus", "ON",
            ],
        )

        objects = list_all_objects(s3_client, locked_bucket, prefix=prefix)
        assert len(objects) == 1

        status = get_object_legal_hold(s3_client, locked_bucket, objects[0]["Key"])
        assert status == "ON"

    def test_legal_hold_off_visible_via_boto3(self, elbencho, s3_client, locked_bucket):
        """Legal hold OFF set by elbencho is independently confirmed as OFF through the S3 API."""
        prefix = random_prefix()
        elbencho.write_objects(
            [locked_bucket], files=1, size="4k", block="4k",
            extra_args=[
                "--s3objprefix", prefix,
                "--s3olegalhold",
                "--s3olegalholdstatus", "OFF",
            ],
        )

        objects = list_all_objects(s3_client, locked_bucket, prefix=prefix)
        assert len(objects) == 1

        status = get_object_legal_hold(s3_client, locked_bucket, objects[0]["Key"])
        assert status == "OFF"

    def test_delete_rejected_while_legal_hold_on(self, elbencho, s3_client, locked_bucket):
        """DeleteObject must be refused by S3 while a legal hold is active on the object version."""
        prefix = random_prefix()
        elbencho.write_objects(
            [locked_bucket], files=1, size="4k", block="4k",
            extra_args=[
                "--s3objprefix", prefix,
                "--s3olegalhold",
                "--s3olegalholdstatus", "ON",
            ],
        )

        objects = list_all_objects(s3_client, locked_bucket, prefix=prefix)
        key = objects[0]["Key"]
        version_id = s3_client.head_object(Bucket=locked_bucket, Key=key)["VersionId"]

        with pytest.raises(ClientError) as exc:
            s3_client.delete_object(
                Bucket=locked_bucket, Key=key, VersionId=version_id,
            )
        err = exc.value.response["Error"]["Code"]
        status = exc.value.response["ResponseMetadata"]["HTTPStatusCode"]
        assert (err == "AccessDenied" and status == 403) or (
            err == "InvalidRequest" and status == 400
        )

