import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    json_result: dict = field(default_factory=dict)
    command: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0


class ElbenchoRunner:
    """Invokes elbencho CLI and captures structured output."""

    def __init__(
        self,
        binary: str = "elbencho",
        endpoint: str | None = None,
        access_key: str = "",
        secret_key: str = "",
        region: str = "us-west-1",
        session_token: str | None = None,
    ):
        self.binary = binary
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.session_token = session_token or ""

    def _base_s3_args(self) -> list[str]:
        endpoint = self.endpoint or f"https://s3.{self.region}.amazonaws.com"
        args = [
            "--s3endpoints", endpoint,
            "--s3region", self.region,
        ]
        if self.access_key and self.secret_key:
            args += [
                "--s3key",
                self.access_key,
                "--s3secret",
                self.secret_key,
            ]
            if self.session_token:
                args += ["--s3sessiontoken", self.session_token]
        return args

    def run(
        self,
        args: list[str],
        buckets: list[str] | None = None,
        timeout: int = 120,
        expect_fail: bool = False,
    ) -> RunResult:
        with tempfile.NamedTemporaryFile(suffix=".json", prefix="elbencho_", delete=True) as tmp:
            json_path = tmp.name

            cmd = [self.binary] + self._base_s3_args()
            cmd += ["--jsonfile", json_path]
            cmd += args
            if buckets:
                cmd += buckets

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            json_result = {}
            if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
                with open(json_path) as f:
                    raw = f.read().strip()
                    if raw:
                        try:
                            json_result = json.loads(raw)
                        except json.JSONDecodeError:
                            pass

            result = RunResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                json_result=json_result,
                command=cmd,
            )

            if not expect_fail and not result.succeeded:
                raise ElbenchoError(result)

            return result

    def create_buckets(self, buckets: list[str], **kwargs) -> RunResult:
        return self.run(["-d", "--no0usecerr"], buckets=buckets, **kwargs)

    def delete_buckets(self, buckets: list[str], **kwargs) -> RunResult:
        return self.run(["-D", "--no0usecerr"], buckets=buckets, **kwargs)

    def write_objects(
        self,
        buckets: list[str],
        threads: int = 1,
        dirs: int = 0,
        files: int = 1,
        size: str = "1m",
        block: str = "1m",
        extra_args: list[str] | None = None,
        **kwargs,
    ) -> RunResult:
        args = [
            "-w", "--no0usecerr",
            "-t", str(threads),
            "-n", str(dirs),
            "-N", str(files),
            "-s", size,
            "-b", block,
        ]
        if extra_args:
            args += extra_args
        return self.run(args, buckets=buckets, **kwargs)

    def read_objects(
        self,
        buckets: list[str],
        threads: int = 1,
        dirs: int = 0,
        files: int = 1,
        size: str = "1m",
        block: str = "1m",
        extra_args: list[str] | None = None,
        **kwargs,
    ) -> RunResult:
        args = [
            "-r", "--no0usecerr",
            "-t", str(threads),
            "-n", str(dirs),
            "-N", str(files),
            "-s", size,
            "-b", block,
        ]
        if extra_args:
            args += extra_args
        return self.run(args, buckets=buckets, **kwargs)

    def delete_objects(
        self,
        buckets: list[str],
        threads: int = 1,
        dirs: int = 0,
        files: int = 1,
        extra_args: list[str] | None = None,
        **kwargs,
    ) -> RunResult:
        args = [
            "-F", "--no0usecerr",
            "-t", str(threads),
            "-n", str(dirs),
            "-N", str(files),
        ]
        if extra_args:
            args += extra_args
        return self.run(args, buckets=buckets, **kwargs)

    def stat_buckets(self, buckets: list[str], **kwargs) -> RunResult:
        return self.run(["--s3statdirs", "--no0usecerr"], buckets=buckets, **kwargs)

    def copy_objects(
        self,
        buckets: list[str],
        threads: int = 1,
        dirs: int = 0,
        files: int = 1,
        size: str = "4k",
        block: str = "4k",
        src_bucket: str | None = None,
        src_prefix: str | None = None,
        dst_prefix: str | None = None,
        extra_args: list[str] | None = None,
        **kwargs,
    ) -> RunResult:
        args = [
            "--s3copyobj", "--no0usecerr",
            "-t", str(threads),
            "-n", str(dirs),
            "-N", str(files),
            "-s", size,
            "-b", block,
        ]
        if src_bucket:
            args += ["--s3copybucket", src_bucket]
        if src_prefix:
            args += ["--s3copysrcpfx", src_prefix]
        if dst_prefix:
            args += ["--s3objprefix", dst_prefix]
        if extra_args:
            args += extra_args
        return self.run(args, buckets=buckets, **kwargs)

    def list_objects(
        self,
        buckets: list[str],
        max_keys: int = 1000,
        prefix: str | None = None,
        extra_args: list[str] | None = None,
        **kwargs,
    ) -> RunResult:
        args = ["--s3listobj", str(max_keys), "--no0usecerr"]
        if prefix:
            args += ["--s3objprefix", prefix]
        if extra_args:
            args += extra_args
        return self.run(args, buckets=buckets, **kwargs)


class ElbenchoError(Exception):
    def __init__(self, result: RunResult):
        self.result = result
        cmd_str = " ".join(result.command)
        super().__init__(
            f"elbencho failed (exit {result.exit_code})\n"
            f"  cmd: {cmd_str}\n"
            f"  stderr: {result.stderr[:500]}"
        )
