"""Tests for the optional cloud backends.

None of the Google libraries and no redis-py are installed here, which is the
point: this is what a community's own machine looks like, and it is the
configuration the project promises keeps working. So these tests check the
behavior that matters when a cloud backend is absent or broken. That the local
backend is chosen, that asking for a missing one produces an instruction rather
than a traceback, and that the two rate limiters answer identically.

The Redis path is exercised through a fake client, because its logic is worth
testing and a test suite that needs a Redis server is a test suite that does not
get run.
"""

from __future__ import annotations

import inspect
import os
import sys
import tempfile
from importlib import util as importlib_util
from typing import Any, Dict, List, Optional

from api.auth import RateLimiter, _build_rate_limiter, rate_limiter_status
from cloud import CloudUnavailable, cloud_status
from cloud.logging_sink import (
    OPERATIONAL_FIELDS, CloudLoggingSink, get_sink, logging_status,
    reset_sink, retention_command, scrub,
)
from cloud.ratelimit import RedisRateLimiter, ratelimit_status, safe_url
from cloud.secrets import (
    clear_cache, is_secret_uri, parse_secret_uri, resolve_env, resolve_secret,
    secrets_status,
)
from cloud.storage import (
    GCSStorage, LocalStorage, StorageError, build_storage, local_path,
    parse_gs_uri, reset_storage, safe_filename, storage_status,
)

PASS: List[str] = []
FAIL: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if not condition else ""))


def installed(package: str) -> bool:
    """Whether a client library is present, so a test can say which world it is in."""
    try:
        return importlib_util.find_spec(package) is not None
    except (ImportError, ValueError):
        return False


class FakeRedis:
    """The smallest Redis that can answer this module's questions.

    Keeps counters and expiry times against a clock the test controls, so a
    window can be crossed without sleeping through one.
    """

    def __init__(self, clock, scripting: bool = True) -> None:
        self.clock = clock
        self.scripting = scripting
        self.values: Dict[str, int] = {}
        self.expiry: Dict[str, float] = {}
        self.commands: List[str] = []

    def _sweep(self) -> None:
        now = self.clock()
        for key in [k for k, at in self.expiry.items() if at <= now]:
            self.values.pop(key, None)
            self.expiry.pop(key, None)

    def incr(self, key: str) -> int:
        self._sweep()
        self.commands.append("incr")
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, ttl: int) -> bool:
        self.commands.append("expire")
        self.expiry[key] = self.clock() + int(ttl)
        return True

    def ttl(self, key: str) -> int:
        self._sweep()
        self.commands.append("ttl")
        if key not in self.values:
            return -2
        if key not in self.expiry:
            return -1
        return max(int(self.expiry[key] - self.clock()), 0)

    def delete(self, key: str) -> None:
        self.values.pop(key, None)
        self.expiry.pop(key, None)

    def scan_iter(self, match: Optional[str] = None):
        return list(self.values)

    def eval(self, script: str, numkeys: int, key: str, ttl: int):
        """What the Lua script does, done in Python."""
        if not self.scripting:
            raise RuntimeError("ERR unknown command 'EVAL'")
        self.commands.append("eval")
        count = self.incr(key)
        if count == 1:
            self.expire(key, ttl)
        return [count, self.ttl(key)]


class BrokenRedis(FakeRedis):
    """A Redis that has gone away mid-flight, which is the interesting failure."""

    def incr(self, key: str) -> int:
        raise ConnectionError("Error 111 connecting to 10.0.0.3:6379. Connection refused.")

    def eval(self, *args):
        raise ConnectionError("Error 111 connecting to 10.0.0.3:6379. Connection refused.")


class Clock:
    """A clock a test can move."""

    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def without_env(*names: str):
    """Remove environment variables and hand back what was there."""
    saved = {name: os.environ.pop(name, None) for name in names}
    return saved


def restore_env(saved: Dict[str, Optional[str]]) -> None:
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def test_local_is_the_default() -> None:
    print("\nnothing configured means nothing cloud")
    saved = without_env("COMMUNITY_REDIS_URL", "COMMUNITY_STORAGE_BUCKET",
                        "COMMUNITY_CLOUD_LOGGING")
    clear_cache()
    try:
        limiter = _build_rate_limiter()
        check("the rate limiter is the in-memory one",
              isinstance(limiter, RateLimiter), type(limiter).__name__)
        check("and says so", limiter.status()["backend"] == "memory")
        check("without claiming it was configured",
              limiter.status()["configured"] is False)

        check("storage is local disk", build_storage().backend == "local")
        check("secrets are used as written", secrets_status()["backend"] == "plain")
        check("request logs are JSONL", logging_status()["backend"] == "jsonl")
        check("no sink is built at all", get_sink() is None)

        status = cloud_status()
        check("cloud-status reports nothing configured",
              status["cloud_configured"] is False, str(status["cloud_configured"]))
        check("and nothing degraded", status["degraded"] == [], str(status["degraded"]))
        for section in ("rate_limits", "storage", "secrets", "request_logs"):
            check(f"cloud-status covers {section}", section in status)
            check(f"{section} names a backend and is active",
                  bool(status[section].get("backend")) and status[section].get("active") is True,
                  str(status[section]))
    finally:
        restore_env(saved)
        clear_cache()


def test_missing_libraries_degrade_with_an_instruction() -> None:
    print("\na library that is not installed")
    saved = without_env("COMMUNITY_REDIS_URL", "COMMUNITY_STORAGE_BUCKET",
                        "COMMUNITY_CLOUD_LOGGING")
    clear_cache()
    try:
        os.environ["COMMUNITY_REDIS_URL"] = "redis://10.0.0.3:6379/0"
        limiter = _build_rate_limiter()
        if installed("redis"):
            check("redis-py is installed here, so only the interface is checked",
                  callable(getattr(limiter, "check", None)))
        else:
            check("a missing redis falls back instead of crashing",
                  isinstance(limiter, RateLimiter), type(limiter).__name__)
            status = limiter.status()
            check("the fallback is reported, not hidden",
                  status["configured"] is True and status["active"] is False, str(status))
            check("the remedy names the package",
                  "pip install redis" in (status["remedy"] or ""), str(status["remedy"]))
            check("and names the way out",
                  "COMMUNITY_REDIS_URL" in (status["remedy"] or ""), str(status["remedy"]))
            check("requests are still served while degraded",
                  limiter.check("someone", 2)[0] is True)

        os.environ["COMMUNITY_STORAGE_BUCKET"] = "brookline-uploads"
        reset_storage()
        storage = build_storage()
        if installed("google.cloud.storage"):
            check("google-cloud-storage is installed here, so only the interface is checked",
                  callable(getattr(storage, "save", None)))
        else:
            check("a missing google-cloud-storage falls back to local disk",
                  storage.backend == "local", storage.backend)
            status = storage_status()
            check("cloud-status calls the bucket configured but inactive",
                  status["configured"] is True and status["active"] is False, str(status))
            check("the remedy names the package",
                  "pip install google-cloud-storage" in (status["remedy"] or ""),
                  str(status["remedy"]))
            check("the detail names the bucket that is not being used",
                  "brookline-uploads" in status["detail"], status["detail"])

        os.environ["COMMUNITY_CLOUD_LOGGING"] = "true"
        sink = get_sink()
        check("a sink is built from configuration alone", sink is not None)
        record = {"ts": "2026-09-20T10:00:00", "endpoint": "/community/ask",
                  "status": "ok", "question_hash": "abc123"}
        if not installed("google.cloud.logging"):
            check("emitting without the library returns False rather than raising",
                  sink.emit("brookline-ma", record) is False)
            status = logging_status()
            check("the local JSONL is still the record",
                  status["backend"] == "jsonl" and status["local_jsonl"] is True, str(status))
            check("the remedy names the package",
                  "pip install google-cloud-logging" in (status["remedy"] or ""),
                  str(status["remedy"]))

        if not installed("google.cloud.secretmanager"):
            missing = resolve_secret("sm://projects/p/secrets/anthropic-key/versions/latest")
            check("an unresolvable secret becomes nothing, not the URI",
                  missing is None, repr(missing))
            status = secrets_status()
            check("the failure is reported", status["active"] is False, str(status))
            check("the remedy names the package",
                  "pip install google-cloud-secret-manager" in (status["remedy"] or ""),
                  str(status["remedy"]))

        degraded = cloud_status()["degraded"]
        expected = {"storage", "secrets", "request_logs"} - {
            "storage" if installed("google.cloud.storage") else "",
            "secrets" if installed("google.cloud.secretmanager") else "",
            "request_logs" if installed("google.cloud.logging") else "",
        }
        check("cloud-status lists every backend that fell back",
              expected.issubset(set(degraded)), f"{degraded} vs {expected}")
    finally:
        restore_env(saved)
        reset_storage()
        reset_sink()
        clear_cache()


def test_local_storage_round_trip() -> None:
    print("\nuploads on local disk")
    with tempfile.TemporaryDirectory() as tmp:
        storage = LocalStorage(tmp)
        uri = storage.save("brookline-ma", "Capital Plan FY26.pdf", b"%PDF-1.7 budget")

        check("save returns a file:// URI", uri.startswith("file://"), uri)
        check("the file lands under the project's uploads directory",
              "/brookline-ma/uploads/" in uri, uri)
        check("it exists", storage.exists(uri))
        with storage.open(uri) as handle:
            check("it reads back byte for byte", handle.read() == b"%PDF-1.7 budget")

        check("a bare path still resolves, for sources stored before this existed",
              storage.exists(str(local_path(uri))))

        escaped = storage.save("brookline-ma", "../../../etc/passwd.pdf", b"x")
        check("a filename cannot escape the project directory",
              "/brookline-ma/uploads/passwd.pdf" in escaped, escaped)
        check("and cannot carry a separator", ".." not in escaped, escaped)
        check("spaces become something a bucket will accept",
              safe_filename("Capital Plan FY26.pdf") == "Capital_Plan_FY26.pdf",
              safe_filename("Capital Plan FY26.pdf"))
        check("an empty name still produces one", safe_filename("") == "upload")

        check("delete removes it", storage.delete(uri) and not storage.exists(uri))
        check("deleting something already gone is not an error",
              storage.delete(uri) is False)
        check("a missing object does not exist", storage.exists(uri) is False)

        try:
            storage.open(uri)
            check("reading a missing object explains itself", False, "no error raised")
        except StorageError as exc:
            check("reading a missing object explains itself", True)
            check("and names the Cloud Storage way out",
                  "COMMUNITY_STORAGE_BUCKET" in str(exc), str(exc))

        try:
            storage.open("gs://a-bucket/uploads/plan.pdf")
            check("a gs:// URI on a local backend explains itself", False, "no error raised")
        except StorageError as exc:
            check("a gs:// URI on a local backend explains itself", True)
            check("and names the variable to set",
                  "COMMUNITY_STORAGE_BUCKET" in str(exc), str(exc))

        check("gs:// URIs parse", parse_gs_uri("gs://bucket/uploads/a.pdf")
              == ("bucket", "uploads/a.pdf"))
        check("the status reports the real directory",
              tmp in storage.status()["location"], storage.status()["location"])


class FakeBlob:
    def __init__(self, bucket: "FakeBucket", key: str) -> None:
        self.bucket, self.key = bucket, key

    def upload_from_string(self, data, content_type=""):
        self.bucket.objects[self.key] = (data, content_type)

    def download_as_bytes(self):
        if self.key not in self.bucket.objects:
            raise RuntimeError("404 No such object")
        return self.bucket.objects[self.key][0]

    def exists(self):
        return self.key in self.bucket.objects

    def delete(self):
        if self.key not in self.bucket.objects:
            raise RuntimeError("404 No such object")
        del self.bucket.objects[self.key]


class FakeBucket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.objects: Dict[str, Any] = {}

    def blob(self, key: str) -> FakeBlob:
        return FakeBlob(self, key)


class FakeGCSClient:
    """A bucket that lives in a dict, so the gs:// path is testable without GCP."""

    def __init__(self) -> None:
        self.buckets: Dict[str, FakeBucket] = {}

    def bucket(self, name: str) -> FakeBucket:
        return self.buckets.setdefault(name, FakeBucket(name))


def test_gcs_object_round_trip() -> None:
    print("\nuploads in a bucket")
    client = FakeGCSClient()
    remote = GCSStorage("brookline-uploads", client=client)
    uri = remote.save("brookline-ma", "Capital Plan FY26.pdf", b"%PDF-1.7 budget")

    check("save returns a gs:// URI", uri.startswith("gs://"), uri)
    check("the object key is namespaced by project and prefix",
          uri == "gs://brookline-uploads/uploads/brookline-ma/Capital_Plan_FY26.pdf", uri)
    check("it exists", remote.exists(uri))
    with remote.open(uri) as handle:
        check("it reads back byte for byte", handle.read() == b"%PDF-1.7 budget")
    check("the PDF is stored with its own content type",
          client.buckets["brookline-uploads"].objects[
              "uploads/brookline-ma/Capital_Plan_FY26.pdf"][1] == "application/pdf")
    check("delete removes it", remote.delete(uri) and not remote.exists(uri))
    check("deleting something already gone is not an error",
          remote.delete(uri) is False)

    try:
        remote.open(uri)
        check("reading a missing object explains itself", False, "no error raised")
    except StorageError as exc:
        check("reading a missing object explains itself", True)
        check("and names the service account as a cause",
              "service account" in str(exc), str(exc))


def test_gcs_keeps_older_local_uploads_readable() -> None:
    print("\nmoving to a bucket does not orphan what is already ingested")
    with tempfile.TemporaryDirectory() as tmp:
        local = LocalStorage(tmp)
        uri = local.save("brookline-ma", "zoning.pdf", b"%PDF old upload")

        # A bucket client is never built: every call here is a file:// one.
        remote = GCSStorage("brookline-uploads", client=object(), data_root=tmp)
        check("a file:// URI is still read from disk", remote.exists(uri))
        with remote.open(uri) as handle:
            check("and still reads back", handle.read() == b"%PDF old upload")
        check("a file:// URI is still deletable", remote.delete(uri))
        check("the object key is namespaced by project",
              remote.key_for("brookline-ma", "zoning.pdf")
              == "uploads/brookline-ma/zoning.pdf",
              remote.key_for("brookline-ma", "zoning.pdf"))
        check("a bucket with no name is refused with a remedy",
              _refuses_empty_bucket(), "empty bucket accepted")


def _refuses_empty_bucket() -> bool:
    try:
        GCSStorage("")
    except CloudUnavailable as exc:
        return "COMMUNITY_STORAGE_BUCKET" in exc.remedy
    return False


def test_secret_references() -> None:
    print("\nsm:// references")
    saved = without_env("COMMUNITY_GCP_PROJECT", "GOOGLE_CLOUD_PROJECT", "GCP_PROJECT")
    clear_cache()
    try:
        check("a plain key passes through untouched",
              resolve_secret("sk-ant-abc123") == "sk-ant-abc123")
        check("an empty value passes through", resolve_secret("") == "")
        check("None passes through", resolve_secret(None) is None)
        check("a header with no reference passes through",
              resolve_secret("Authorization: Bearer tunnel-token")
              == "Authorization: Bearer tunnel-token")
        check("a non-string passes through", resolve_secret(42) == 42)
        check("is_secret_uri only matches the scheme",
              is_secret_uri("sm://x") and not is_secret_uri("smtp://x")
              and not is_secret_uri(None))

        full = "sm://projects/brookline/secrets/anthropic-key/versions/3"
        check("the full form parses",
              parse_secret_uri(full) == "projects/brookline/secrets/anthropic-key/versions/3",
              parse_secret_uri(full))
        check("a missing version becomes latest",
              parse_secret_uri("sm://projects/brookline/secrets/tunnel")
              == "projects/brookline/secrets/tunnel/versions/latest")

        try:
            parse_secret_uri("sm://anthropic-key")
            check("a short form with no project is refused", False, "accepted")
        except ValueError as exc:
            check("a short form with no project is refused", True)
            check("the refusal names the variables to set",
                  "GOOGLE_CLOUD_PROJECT" in str(exc), str(exc))

        os.environ["GOOGLE_CLOUD_PROJECT"] = "brookline"
        check("with a project, the short form parses",
              parse_secret_uri("sm://anthropic-key")
              == "projects/brookline/secrets/anthropic-key/versions/latest",
              parse_secret_uri("sm://anthropic-key"))
        check("the short form takes a version too",
              parse_secret_uri("sm://anthropic-key/versions/7")
              == "projects/brookline/secrets/anthropic-key/versions/7")

        for malformed in ["sm://", "sm://projects/brookline", "sm://projects/b/keys/x"]:
            try:
                parse_secret_uri(malformed)
                check(f"{malformed!r} is refused", False, "accepted")
            except ValueError:
                check(f"{malformed!r} is refused", True)

        try:
            parse_secret_uri("not-a-reference")
            check("a plain value is not parsed as a reference", False, "accepted")
        except ValueError:
            check("a plain value is not parsed as a reference", True)

        os.environ["COMMUNITY_TEST_KEY"] = "plain-value"
        check("resolve_env passes a plain variable through",
              resolve_env("COMMUNITY_TEST_KEY") == "plain-value")
        check("an absent variable returns the default",
              resolve_env("COMMUNITY_ABSENT_KEY", "fallback") == "fallback")
        os.environ.pop("COMMUNITY_TEST_KEY", None)

        if not installed("google.cloud.secretmanager"):
            header = "Authorization: Bearer sm://projects/b/secrets/tunnel/versions/latest"
            check("an embedded reference that cannot be resolved drops the value",
                  resolve_secret(header) is None, repr(resolve_secret(header)))
            check("a resident's question is never what breaks: the value is simply absent",
                  resolve_secret(header, default="") == "")
            failures = secrets_status()["failures"]
            check("the failure is recorded against the resource name",
                  any("secrets/tunnel" in name for name in failures), str(failures))
            check("and is remembered rather than retried per question",
                  len(failures) == 1, str(failures))
    finally:
        restore_env(saved)
        clear_cache()


def test_rate_limiter_backends_agree() -> None:
    print("\nthe two rate limiters answer identically")
    clock = Clock()
    shared = RedisRateLimiter(client=FakeRedis(clock), window_seconds=60, clock=clock)
    local = RateLimiter(window_seconds=60)

    check("both expose check with the same signature",
          inspect.signature(shared.check) == inspect.signature(local.check),
          f"{inspect.signature(shared.check)} vs {inspect.signature(local.check)}")
    for method in ("check", "reset", "status"):
        check(f"both expose {method}", callable(getattr(shared, method, None))
              and callable(getattr(local, method, None)))

    redis_results = [shared.check("app-1", 3) for _ in range(5)]
    local_results = [local.check("app-1", 3) for _ in range(5)]
    check("allowed matches", [r[0] for r in redis_results] == [r[0] for r in local_results],
          f"{redis_results} vs {local_results}")
    check("remaining matches", [r[1] for r in redis_results] == [r[1] for r in local_results],
          f"{redis_results} vs {local_results}")
    check("a denial reports a retry-after of at least a second",
          redis_results[3][2] >= 1 and local_results[3][2] >= 1, str(redis_results[3]))

    check("no limit means no limiting",
          shared.check("app-2", 0) == local.check("app-2", 0) == (True, -1, 0))
    check("keys are counted separately", shared.check("app-3", 1)[0] is True)

    clock.advance(61)
    check("the window resets when it expires", shared.check("app-1", 3) == (True, 2, 0),
          str(shared.check("app-1", 3)))

    print("\none counter, several instances")
    counter = FakeRedis(Clock(2_000_000.0))
    instances = [RedisRateLimiter(client=counter, window_seconds=60,
                                  clock=counter.clock) for _ in range(4)]
    verdicts = [instances[i % 4].check("app-1", 3)[0] for i in range(5)]
    check("four instances share one limit rather than four",
          verdicts == [True, True, True, False, False], str(verdicts))

    scripted = FakeRedis(Clock(), scripting=True)
    RedisRateLimiter(client=scripted, window_seconds=60, clock=scripted.clock).check("a", 5)
    check("counting is one atomic call when the server runs EVAL",
          scripted.commands[0] == "eval", str(scripted.commands))

    plain = FakeRedis(Clock(), scripting=False)
    limiter = RedisRateLimiter(client=plain, window_seconds=60, clock=plain.clock)
    check("a Redis without scripting still counts correctly",
          [limiter.check("a", 2)[0] for _ in range(3)] == [True, True, False])
    check("and the window still gets an expiry", "expire" in plain.commands,
          str(plain.commands))
    check("which the status reports honestly",
          limiter.status()["atomic"] == "incr+expire", limiter.status()["atomic"])


def test_redis_outage_never_reaches_a_resident() -> None:
    print("\nRedis going away")
    clock = Clock()
    limiter = RedisRateLimiter("redis://user:hunter2@10.0.0.3:6379/0",
                               client=BrokenRedis(clock), window_seconds=60,
                               clock=clock, fallback=RateLimiter(60))

    verdicts = [limiter.check("app-1", 3) for _ in range(5)]
    check("questions are still answered", [v[0] for v in verdicts]
          == [True, True, True, False, False], str(verdicts))
    check("the fallback is still a limit, not an open door",
          verdicts[3][0] is False, str(verdicts[3]))

    status = limiter.status()
    check("the limiter knows it is degraded", status["active"] is False, str(status))
    check("the detail says what the community lost",
          "per process" in status["detail"], status["detail"])
    check("the error is kept for the operator",
          "ConnectionError" in (status["last_error"] or ""), str(status["last_error"]))
    check("the remedy says it recovers on its own",
          "recovers" in (status["remedy"] or ""), str(status["remedy"]))
    check("the password never appears in the status",
          "hunter2" not in str(status), str(status))
    check("safe_url keeps the host and drops the password",
          safe_url("redis://user:hunter2@10.0.0.3:6379/0")
          == "redis://user:***@10.0.0.3:6379/0",
          safe_url("redis://user:hunter2@10.0.0.3:6379/0"))


def test_request_records_keep_their_privacy_rules() -> None:
    print("\nwhat leaves the community's own disk")
    record = {
        "ts": "2026-09-20T10:00:00", "endpoint": "/community/ask",
        "client_id": "c1", "client_name": "Newsletter", "status": "ok",
        "latency_ms": 812.4, "question_hash": "8f14e45fceea167a",
        "question_length": 42, "model": "gemma-4-26b-a4b", "provider": "lmstudio",
        "constitution_version": "1.0", "sources_retrieved": 8, "sources_used": 3,
        "question": "Call me at 617-555-0123 about Article 8.4",
        "resident_email": "someone@example.org",
    }

    default = scrub(record)
    check("question text is dropped by default", "question" not in default, str(default))
    check("operational metadata is kept",
          default["sources_used"] == 3 and default["model"] == "gemma-4-26b-a4b")
    check("the salted hash is kept, so repeats stay countable",
          default["question_hash"] == "8f14e45fceea167a")
    check("a field nobody allowed is dropped, not forwarded",
          "resident_email" not in default, str(default))

    enabled = scrub(record, include_question_text=True)
    check("question text is included only when the project enables it",
          "question" in enabled)
    check("and is redacted again on the way out",
          "617-555-0123" not in enabled["question"], enabled["question"])
    check("the allow-list is what governance.md calls operational",
          "question" not in OPERATIONAL_FIELDS)

    sink = CloudLoggingSink(logger=_CollectingLogger())
    check("emitting a record succeeds",
          sink.emit("brookline-ma", record, retention_days=30) is True)
    written = sink.logger.entries[0]
    check("the project is labeled", written["labels"]["project_id"] == "brookline-ma")
    check("the community's retention is carried with the record",
          written["entry"]["retention_days"] == 30, str(written["entry"]))
    check("question text is still excluded by default",
          "question" not in written["entry"], str(written["entry"]))
    check("an error record is severity ERROR",
          _severity_of_error(sink) == "ERROR")

    check("the retention command names the configured window",
          "--retention-days=30" in retention_command(30), retention_command(30))
    check("keeping records forever is described rather than promised",
          "indefinitely" in retention_command(0), retention_command(0))

    broken = CloudLoggingSink(logger=_FailingLogger())
    check("a sink that cannot write returns False rather than raising",
          broken.emit("brookline-ma", record) is False)
    check("and reports why", "RuntimeError" in (broken.status()["last_error"] or ""),
          str(broken.status()["last_error"]))
    check("while the local JSONL is still the record",
          broken.status()["local_jsonl"] is True)


class _CollectingLogger:
    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def log_struct(self, entry, severity="INFO", labels=None):
        self.entries.append({"entry": entry, "severity": severity, "labels": labels or {}})


class _FailingLogger:
    def log_struct(self, *args, **kwargs):
        raise RuntimeError("403 Logs Writer role missing")


def _severity_of_error(sink: CloudLoggingSink) -> str:
    sink.emit("brookline-ma", {"endpoint": "/community/ask", "status": "error",
                               "error": "provider unreachable"})
    return sink.logger.entries[-1]["severity"]


def test_audit_still_writes_jsonl() -> None:
    print("\nthe local log is untouched by any of this")
    from api.audit import log_request, usage_summary

    saved = without_env("COMMUNITY_CLOUD_LOGGING")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            record = log_request(
                "brookline-ma", endpoint="/community/ask", client_id="c1",
                question="When does the Select Board meet?", data_root=tmp,
                retention_days=30, latency_ms=101.5,
                provenance={"sources_retrieved": 4, "sources_used": 2},
            )
            check("a record is returned", record is not None)
            check("the question is still only a hash",
                  "question" not in record and bool(record["question_hash"]))
            summary = usage_summary("brookline-ma", data_root=tmp)
            check("and the usage summary still reads it", summary["requests"] == 1,
                  str(summary["requests"]))
            check("the summary still counts unique questions",
                  summary["unique_questions"] == 1)
    finally:
        restore_env(saved)


def test_status_endpoint_is_registered() -> None:
    print("\nan operator can see all of this without guessing")
    from tests.test_app_wiring import _install_stubs

    _install_stubs()
    try:
        import app
    except Exception as exc:
        check("app.py imports with the cloud package wired in", False,
              f"{type(exc).__name__}: {exc}")
        return

    check("app.py imports with the cloud package wired in", True)
    routes = {getattr(r, "path", "") for r in app.app.routes}
    check("/api/admin/cloud-status is registered",
          "/api/admin/cloud-status" in routes)

    body = cloud_status()
    check("it answers with every backend",
          {"rate_limits", "storage", "secrets", "request_logs"} <= set(body),
          str(sorted(body)))
    check("and with a single verdict an operator can read",
          body["cloud_configured"] in (True, False))
    check("the live limiter is what it reports",
          rate_limiter_status()["backend"] == body["rate_limits"]["backend"])
    check("environment-derived status agrees when nothing is configured",
          ratelimit_status()["backend"] == "memory" or bool(os.getenv("COMMUNITY_REDIS_URL")))


def main() -> int:
    print("=" * 62)
    print("Cloud backend tests")
    print("=" * 62)
    for fn in [
        test_local_is_the_default,
        test_missing_libraries_degrade_with_an_instruction,
        test_local_storage_round_trip,
        test_gcs_object_round_trip,
        test_gcs_keeps_older_local_uploads_readable,
        test_secret_references,
        test_rate_limiter_backends_agree,
        test_redis_outage_never_reaches_a_resident,
        test_request_records_keep_their_privacy_rules,
        test_audit_still_writes_jsonl,
        test_status_endpoint_is_registered,
    ]:
        fn()
    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


def test_all() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
