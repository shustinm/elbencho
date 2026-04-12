# S3 integration tests (MinIO and AWS)

These tests live under `tests/s3/`. They call the **elbencho** binary against real S3-compatible storage and use **boto3** to check results and clean up buckets.

---

## What you need first

1. **elbencho built with S3 support** — a binary you can run (e.g. `elbencho` on your `PATH`, or set `ELBENCHO_BIN` to its full path).
2. **[uv](https://docs.astral.sh/uv/)** — install with `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`.
3. A shell where you can set environment variables for that session.

All commands below assume your **repo root** is the current directory.

---

## Configuration

Credentials and endpoint can be passed as **pytest CLI options** or **environment variables**. CLI options take precedence.

All defaults are set for a local MinIO instance, so running `uv run pytest` with no arguments works out of the box against MinIO on `http://127.0.0.1:9000`.


| pytest option        | Environment variable fallback | Default                 | Description             |
| -------------------- | ----------------------------- | ----------------------- | ----------------------- |
| `--s3key`            | `AWS_ACCESS_KEY_ID`           | `minioadmin`            | S3 access key           |
| `--s3secret`         | `AWS_SECRET_ACCESS_KEY`       | `minioadmin`            | S3 secret key           |
| `--s3endpoints`      | `AWS_ENDPOINT_URL_S3`         | `http://127.0.0.1:9000` | S3 endpoint URL         |
| `--s3region`         | `AWS_DEFAULT_REGION`          | `us-west-1`             | S3 region               |
| `--s3sessiontoken`   | `AWS_SESSION_TOKEN`           | *(empty)*               | Session token (STS)     |
| `--elbencho-bin`     | `ELBENCHO_BIN`                | `elbencho`              | Path to elbencho binary |
| `--s3-bucket-prefix` | `S3_TEST_BUCKET_PREFIX`       | *(empty)*               | Prefix for bucket names |


---

## Part 1 — Run tests against **MinIO**

### Step 1: Start MinIO

Example with Docker (API on port 9000):

```bash
docker run -d --name minio-test \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

Default credentials: **minioadmin** / **minioadmin**. API URL: `http://127.0.0.1:9000`.

### Step 2: Run pytest

With defaults (no env vars needed for a standard local MinIO):

```bash
uv run --directory tests pytest s3/ -v --tb=short
```

`uv run` automatically creates the virtualenv and installs dependencies on first use.

Or override via environment variables:

```bash
export AWS_ENDPOINT_URL_S3="http://127.0.0.1:9000"
export AWS_ACCESS_KEY_ID="minioadmin"
export AWS_SECRET_ACCESS_KEY="minioadmin"
export ELBENCHO_BIN="../bin/elbencho"
uv run --directory tests pytest s3/ -v --tb=short
```

Or pass options directly on the command line:

```bash
uv run --directory tests pytest s3/ -v --tb=short \
  --s3endpoints="http://127.0.0.1:9000" \
  --s3key=minioadmin \
  --s3secret=minioadmin
```

### MinIO notes

- Multipart-related tests use part sizes that respect the **5 MiB** minimum (same rule as S3).
- Some behaviors (ACLs, edge cases) can differ from AWS; failures there are often product/API differences, not pytest wiring.

---

## Part 2 — Run tests against **AWS**

### Step 1: Credentials

Set static IAM keys (or STS temporary credentials) and **override the MinIO defaults**:

```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-west-1"
export AWS_ENDPOINT_URL_S3=""
```

If you use **temporary** credentials (STS), also set:

```bash
export AWS_SESSION_TOKEN="..."
```

If you use **SSO**, export the credentials into the current shell first:

```bash
aws sso login --profile my-profile
eval "$(aws configure export-credentials --profile my-profile --format env)"
export AWS_DEFAULT_REGION="us-west-1"
export AWS_ENDPOINT_URL_S3=""
```

Setting `AWS_ENDPOINT_URL_S3` to empty overrides the MinIO default so the SDK uses the standard regional endpoint.

### Step 2: Optional settings

```bash
export ELBENCHO_BIN="/path/to/elbencho"
```

On a **shared AWS account**, avoid bucket name clashes:

```bash
export S3_TEST_BUCKET_PREFIX="yourname-"
```

### Step 3: Run pytest

```bash
uv run --directory tests pytest s3/ -v -s --tb=short
```

Your IAM principal needs permissions to **create/delete buckets** and perform normal S3 object operations in the chosen region.

---

## Cheatsheet (copy-paste)

**MinIO (all defaults — just start MinIO and run)**

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_DEFAULT_REGION
export ELBENCHO_BIN="../bin/elbencho"
uv run --directory tests pytest s3/ -v -s --tb=short
```

**AWS — SSO (export credentials first)**

```bash
export AWS_ENDPOINT_URL_S3="https://us-east-1.amazonaws.com"
export AWS_DEFAULT_REGION="us-east-1"
export ELBENCHO_BIN="../bin/elbencho"
export S3_TEST_BUCKET_PREFIX="vastdata-infra-s3-"
aws sso login --profile my-profile
eval "$(aws configure export-credentials --profile my-profile --format env)"
uv run --directory tests pytest s3/ -v -s --tb=short
```

**AWS — static IAM keys**

```bash
export AWS_ENDPOINT_URL_S3=""
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-west-1"
export S3_TEST_BUCKET_PREFIX="vastdata-infra-s3-"
export ELBENCHO_BIN="../bin/elbencho"
# optional for STS:
# export AWS_SESSION_TOKEN="..."
uv run --directory tests pytest s3/ -v -s --tb=short
```

---

## Troubleshooting


| Symptom                                  | What to check                                                                                                      |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Connection refused                       | MinIO running; `AWS_ENDPOINT_URL_S3` host/port                                                                     |
| `InvalidTokenId` / bad signature (MinIO) | Stray `AWS_SESSION_TOKEN` with MinIO keys — unset it                                                               |
| No credentials                           | Set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`, or for SSO use `eval "$(aws configure export-credentials ...)"` |
| `elbencho` not found                     | `ELBENCHO_BIN` or install binary on `PATH`                                                                         |
| `AccessDenied` on AWS                    | IAM policy for `s3:CreateBucket`, `s3:DeleteBucket`, object read/write/delete in that region                       |


---

## How the tests behave

- Fixture `**bucket**` creates one regular bucket per test session.
- Fixture `**locked_bucket**` creates one object-lock-enabled bucket per test session.
- Tests should isolate object keys with `helpers.s3_utils.random_prefix()` and pass `--s3objprefix`.

