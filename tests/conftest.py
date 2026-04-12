import os
import uuid
from dataclasses import dataclass
from typing import Iterable

import pytest

from mypy_boto3_s3.client import S3Client

from helpers.elbencho import ElbenchoRunner
from helpers.s3_utils import force_delete_bucket, force_delete_locked_bucket, make_s3_client


@dataclass(frozen=True)
class TestConfig:
    endpoint: str | None
    access_key: str
    secret_key: str
    region: str
    session_token: str | None
    binary: str
    bucket_prefix: str


def pytest_addoption(parser):
    parser.addoption(
        "--s3key",
        action="store",
        default=os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
        help="S3 access key (falls back to AWS_ACCESS_KEY_ID env)",
    )
    parser.addoption(
        "--s3secret",
        action="store",
        default=os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"),
        help="S3 secret key (falls back to AWS_SECRET_ACCESS_KEY env)",
    )
    parser.addoption(
        "--s3endpoints",
        action="store",
        default=os.getenv("AWS_ENDPOINT_URL_S3", "http://127.0.0.1:9000"),
        help="S3 endpoint URL (falls back to AWS_ENDPOINT_URL_S3 env)",
    )
    parser.addoption(
        "--s3region",
        action="store",
        default=os.getenv("AWS_DEFAULT_REGION", "us-west-1"),
        help="S3 region (falls back to AWS_DEFAULT_REGION env)",
    )
    parser.addoption(
        "--s3sessiontoken",
        action="store",
        default=os.getenv("AWS_SESSION_TOKEN", ""),
        help="S3 session token (falls back to AWS_SESSION_TOKEN env)",
    )
    parser.addoption(
        "--elbencho-bin",
        action="store",
        default=os.getenv("ELBENCHO_BIN", "elbencho"),
        help="Path to elbencho binary (falls back to ELBENCHO_BIN env)",
    )
    parser.addoption(
        "--s3-bucket-prefix",
        action="store",
        default=os.getenv("S3_TEST_BUCKET_PREFIX", ""),
        help="Prefix for generated test bucket names (falls back to S3_TEST_BUCKET_PREFIX env)",
    )


def _build_config(request) -> TestConfig:
    access_key = request.config.getoption("--s3key")
    secret_key = request.config.getoption("--s3secret")

    if not access_key or not secret_key:
        pytest.exit(
            "No S3 credentials. Provide --s3key/--s3secret or set "
            "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars.",
            returncode=2,
        )

    return TestConfig(
        endpoint=request.config.getoption("--s3endpoints") or None,
        access_key=access_key,
        secret_key=secret_key,
        region=request.config.getoption("--s3region"),
        session_token=request.config.getoption("--s3sessiontoken") or None,
        binary=request.config.getoption("--elbencho-bin"),
        bucket_prefix=request.config.getoption("--s3-bucket-prefix"),
    )


@pytest.fixture(scope="session")
def config(request) -> TestConfig:
    return _build_config(request)


@pytest.fixture(scope="session")
def elbencho(config) -> ElbenchoRunner:
    return ElbenchoRunner(
        binary=config.binary,
        endpoint=config.endpoint,
        access_key=config.access_key,
        secret_key=config.secret_key,
        region=config.region,
        session_token=config.session_token,
    )


@pytest.fixture(scope="session")
def s3_client(config) -> S3Client:
    return make_s3_client(
        endpoint=config.endpoint,
        access_key=config.access_key,
        secret_key=config.secret_key,
        region=config.region,
        session_token=config.session_token,
    )


def _bucket_name(prefix: str) -> str:
    return f"{prefix}elbencho-test-{uuid.uuid4().hex[:12]}"


def _create_bucket(s3_client: S3Client, prefix: str, region: str, **kwargs) -> str:
    name = _bucket_name(prefix)
    if region and region != "us-east-1":
        kwargs.setdefault(
            "CreateBucketConfiguration", {"LocationConstraint": region},
        )
    s3_client.create_bucket(Bucket=name, **kwargs)
    return name


@pytest.fixture(scope="session")
def bucket(config, s3_client: S3Client) -> Iterable[str]:
    name = _create_bucket(s3_client, config.bucket_prefix, config.region)
    yield name
    force_delete_bucket(s3_client, name)

@pytest.fixture(scope="session")
def locked_bucket(config: TestConfig, s3_client: S3Client) -> Iterable[str]:
    name = _create_bucket(
        s3_client, config.bucket_prefix, config.region,
        ObjectLockEnabledForBucket=True,
    )
    yield name
    force_delete_locked_bucket(s3_client, name)


@pytest.fixture(scope="session")
def lock_config_bucket(config, s3_client: S3Client) -> Iterable[str]:
    name = _create_bucket(
        s3_client, config.bucket_prefix, config.region,
        ObjectLockEnabledForBucket=True,
    )
    yield name
    force_delete_locked_bucket(s3_client, name)
