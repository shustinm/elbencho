"""Boto3 helpers to verify S3 state (not used by elbencho itself)."""

import sys
import time
import uuid
import warnings
from datetime import datetime, timezone

import boto3
from mypy_boto3_s3 import S3Client

from botocore.config import Config
from botocore.exceptions import ClientError


def make_s3_client(
    endpoint: str | None = None,
    access_key: str = "",
    secret_key: str = "",
    session_token: str | None = None,
    region: str = "us-west-1",
) -> S3Client:
    kwargs: dict = {
        "service_name": "s3",
        "region_name": region,
        "endpoint_url": endpoint or f"https://s3.{region}.amazonaws.com",
        "config": Config(signature_version="s3v4"),
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
    }
    if session_token:
        kwargs["aws_session_token"] = session_token

    return boto3.client(**kwargs)


def random_prefix() -> str:
    return f"t/{uuid.uuid4().hex[:12]}/"


def bucket_exists(client, bucket: str) -> bool:
    try:
        client.head_bucket(Bucket=bucket)
        return True
    except ClientError:
        return False


def list_all_objects(client, bucket: str, prefix: str = "") -> list[dict]:
    objects = []
    kwargs: dict = {"Bucket": bucket}
    if prefix:
        kwargs["Prefix"] = prefix

    while True:
        resp = client.list_objects_v2(**kwargs)
        objects.extend(resp.get("Contents", []))
        if not resp.get("IsTruncated"):
            break
        kwargs["ContinuationToken"] = resp["NextContinuationToken"]

    return objects


def object_exists(client, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def get_object_size(client, bucket: str, key: str) -> int:
    resp = client.head_object(Bucket=bucket, Key=key)
    return resp["ContentLength"]


def get_object_tags(client, bucket: str, key: str) -> dict[str, str]:
    resp = client.get_object_tagging(Bucket=bucket, Key=key)
    return {t["Key"]: t["Value"] for t in resp.get("TagSet", [])}


def get_bucket_tags(client, bucket: str) -> dict[str, str]:
    try:
        resp = client.get_bucket_tagging(Bucket=bucket)
        return {t["Key"]: t["Value"] for t in resp.get("TagSet", [])}
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchTagSet":
            return {}
        raise


def _warn_delete_object_errors(bucket: str, resp: dict) -> None:
    for err in resp.get("Errors", []) or []:
        warnings.warn(
            f"S3 delete_objects failed bucket={bucket!r} key={err.get('Key')!r} "
            f"version_id={err.get('VersionId')!r} code={err.get('Code')!r} "
            f"message={err.get('Message')!r}",
            UserWarning,
            stacklevel=2,
        )


def delete_all_objects(client, bucket: str):
    objects = list_all_objects(client, bucket)
    if not objects:
        return

    for i in range(0, len(objects), 1000):
        batch = objects[i : i + 1000]
        resp = client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": obj["Key"]} for obj in batch]},
        )
        _warn_delete_object_errors(bucket, resp)


def abort_all_multipart_uploads(client, bucket: str) -> None:
    paginator = client.get_paginator("list_multipart_uploads")
    for page in paginator.paginate(Bucket=bucket):
        for upload in page.get("Uploads", []):
            try:
                client.abort_multipart_upload(
                    Bucket=bucket,
                    Key=upload["Key"],
                    UploadId=upload["UploadId"],
                )
            except ClientError:
                pass


def delete_all_object_versions(client, bucket: str) -> None:
    paginator = client.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=bucket):
        to_delete = []
        for v in page.get("Versions", []):
            to_delete.append({"Key": v["Key"], "VersionId": v["VersionId"]})
        for dm in page.get("DeleteMarkers", []):
            to_delete.append({"Key": dm["Key"], "VersionId": dm["VersionId"]})
        if not to_delete:
            continue
        for i in range(0, len(to_delete), 1000):
            batch = to_delete[i : i + 1000]
            resp = client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": batch, "Quiet": True},
            )
            _warn_delete_object_errors(bucket, resp)


def get_object_legal_hold(
    client, bucket: str, key: str, version_id: str | None = None,
) -> str:
    """Return the legal hold status string ('ON' or 'OFF') for the given object."""
    kwargs: dict = {"Bucket": bucket, "Key": key}
    if version_id:
        kwargs["VersionId"] = version_id
    resp = client.get_object_legal_hold(**kwargs)
    return resp.get("LegalHold", {}).get("Status", "")


def get_object_retention(
    client, bucket: str, key: str, version_id: str | None = None,
) -> dict:
    kwargs: dict = {"Bucket": bucket, "Key": key}
    if version_id:
        kwargs["VersionId"] = version_id
    resp = client.get_object_retention(**kwargs)
    return resp.get("Retention", {})


def force_delete_locked_bucket(client: S3Client, bucket: str):
    """Delete a bucket that may contain objects with GOVERNANCE retention.

    Each version is individually unlocked (legal-hold off, retention bypassed)
    and deleted via ``_force_delete_version``.  Every step is independently
    guarded so a single failure never short-circuits the rest of the cleanup.
    """
    try:
        abort_all_multipart_uploads(client, bucket)
    except ClientError:
        pass

    _delete_all_versions_force(client, bucket)

    try:
        delete_all_objects(client, bucket)
    except ClientError:
        pass

    try:
        client.delete_bucket(Bucket=bucket)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        msg = e.response.get("Error", {}).get("Message", "")
        warnings.warn(
            f"S3 locked-bucket cleanup raised ClientError for {bucket!r}: {code} {msg}",
            UserWarning,
            stacklevel=2,
        )

    if bucket_exists(client, bucket):
        warnings.warn(
            f"S3 bucket {bucket!r} still exists after locked-bucket cleanup.",
            UserWarning,
            stacklevel=2,
        )


def _delete_all_versions_force(client, bucket: str) -> None:
    """Unlock and delete every object version and delete marker in the bucket.

    First tries ``BypassGovernanceRetention`` for each version.  If the server
    does not support bypass (``InvalidRequest`` / ``AccessDenied``), falls back
    to waiting until the latest ``RetainUntilDate`` across all locked versions
    and then retries deletion.
    """
    failed: list[tuple[str, str]] = []  # (key, version_id) pairs that need a wait

    paginator = client.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=bucket):
        for v in page.get("Versions", []):
            if not _force_delete_version(client, bucket, v["Key"], v["VersionId"]):
                failed.append((v["Key"], v["VersionId"]))
        for dm in page.get("DeleteMarkers", []):
            try:
                client.delete_object(
                    Bucket=bucket, Key=dm["Key"], VersionId=dm["VersionId"],
                )
            except ClientError:
                pass

    if not failed:
        return

    # Bypass didn't work — find the latest RetainUntilDate across all failed versions
    # and wait exactly until it passes, then retry.
    latest: datetime | None = None
    for key, version_id in failed:
        try:
            retention = get_object_retention(client, bucket, key, version_id=version_id)
            retain_until = retention.get("RetainUntilDate")
            if retain_until is None:
                continue
            if isinstance(retain_until, str):
                retain_until = datetime.fromisoformat(
                    retain_until.replace("Z", "+00:00")
                )
            if retain_until.tzinfo is None:
                retain_until = retain_until.replace(tzinfo=timezone.utc)
            if latest is None or retain_until > latest:
                latest = retain_until
        except ClientError:
            pass

    if latest is not None:
        wait = max(0.0, (latest - datetime.now(timezone.utc)).total_seconds())
        if wait > 0:
            _sleep_with_progress(wait, bucket)

    for key, version_id in failed:
        try:
            client.delete_object(Bucket=bucket, Key=key, VersionId=version_id)
        except ClientError as e:
            warnings.warn(
                f"Could not delete version {key!r} ({version_id!r}) "
                f"in {bucket!r}: {e.response['Error']['Code']} "
                f"{e.response['Error']['Message']}",
                UserWarning,
                stacklevel=3,
            )


def _sleep_with_progress(wait_seconds: float, bucket: str) -> None:
    total = int(wait_seconds) + 1
    desc = f"Waiting for retention to expire ({bucket})"
    for i in range(total):
        remaining = total - i
        if i == 0 or remaining % 5 == 0 or remaining == 1:
            print(f"[locked-bucket-cleanup] {desc}: {remaining}s remaining", file=sys.stderr)
        time.sleep(1)


def _force_delete_version(client, bucket: str, key: str, version_id: str) -> bool:
    """Remove legal hold, attempt bypass of retention, then delete.

    Returns True if the version was successfully deleted, False if it is still
    WORM-protected and needs to wait for ``RetainUntilDate``.
    """
    try:
        client.put_object_legal_hold(
            Bucket=bucket, Key=key, VersionId=version_id,
            LegalHold={"Status": "OFF"},
        )
    except ClientError:
        pass
    try:
        client.put_object_retention(
            Bucket=bucket, Key=key, VersionId=version_id,
            Retention={"Mode": "GOVERNANCE", "RetainUntilDate": "1970-01-01T00:00:00Z"},
            BypassGovernanceRetention=True,
        )
    except ClientError:
        pass
    try:
        client.delete_object(Bucket=bucket, Key=key, VersionId=version_id)
        return True
    except ClientError:
        return False


def force_delete_bucket(client, bucket: str):
    try:
        abort_all_multipart_uploads(client, bucket)
        delete_all_object_versions(client, bucket)
        delete_all_objects(client, bucket)
        client.delete_bucket(Bucket=bucket)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        msg = e.response.get("Error", {}).get("Message", "")
        warnings.warn(
            f"S3 bucket cleanup raised ClientError for {bucket!r}: {code} {msg}",
            UserWarning,
            stacklevel=2,
        )
    if bucket_exists(client, bucket):
        warnings.warn(
            f"S3 bucket {bucket!r} still exists after cleanup.",
            UserWarning,
            stacklevel=2,
        )
