"""Persist inspectable studio runs and coordinate operations across worker processes."""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

LOG = logging.getLogger(__name__)
POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="content-studio")
ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,100}\Z")
DEMO = "watermelon-demo"
_STAGE_WRITER = ContextVar("studio_stage_writer", default=None)


def progress(stage):
    """Publish a worker's actual pipeline stage; ordinary CLI calls need no context."""
    writer = _STAGE_WRITER.get()
    if writer:
        writer(stage)


def record_stage(job, stage):
    at = timestamp()
    job.update(stage=stage, updated_at=at)
    job.setdefault("stages", []).append(
        {"stage": stage, "status": job["status"], "updated_at": at}
    )


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def root():
    return Path(os.getenv("STUDIO_RUNS_DIR", "data/studio/runs")).resolve()


def run_path(run_id):
    if not ID.fullmatch(run_id):
        raise ValueError("Invalid run identifier")
    return root() / run_id


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", dir=path.parent, delete=False, encoding="utf-8"
    ) as stream:
        name = stream.name
        try:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            os.unlink(name)
            raise
    os.replace(name, path)


def load(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


class Busy(Exception):
    pass


@contextmanager
def locked(folder):
    handle = (folder / ".lock").open("a+")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Busy("Another operation is running for this product.") from exc
        yield
    finally:
        handle.close()


def _jobs(folder):
    jobs = [load(p) for p in (folder / "jobs").glob("*.json")]
    if any(j["status"] == "running" for j in jobs):
        try:
            with locked(folder):
                for job in jobs:
                    path = folder / "jobs" / (job["id"] + ".json")
                    # The worker may have finished between our first read and locking.
                    job.update(load(path))
                    if job["status"] == "running":
                        job.update(
                            status="interrupted",
                            error="The worker stopped before this operation finished.",
                        )
                        record_stage(job, "Interrupted")
                        write_json(path, job)
        except Busy:
            pass
    return sorted(jobs, key=lambda j: j["created_at"], reverse=True)[:15]


def fingerprint(*inputs):
    value = json.dumps(inputs, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(value.encode()).hexdigest()


def cached_job(folder, signature, statuses):
    if signature:
        for path in (folder / "jobs").glob("*.json"):
            job = load(path)
            if job.get("signature") == signature and job["status"] in statuses:
                return job
    return None


def submit(folder, action, operation, signature=None):
    # Keep the same advisory lock from admission through publication of the result.
    lock = locked(folder)
    try:
        lock.__enter__()
    except Busy:
        previous = cached_job(folder, signature, {"running"})
        if previous:
            return previous
        raise
    previous = cached_job(folder, signature, {"complete"})
    if previous:
        lock.__exit__(None, None, None)
        return previous
    job = {
        "id": uuid4().hex,
        "action": action,
        "status": "running",
        "created_at": timestamp(),
        "signature": signature,
    }
    path = folder / "jobs" / (job["id"] + ".json")

    def mark(stage):
        record_stage(job, stage)
        write_json(path, job)

    def work():
        token = _STAGE_WRITER.set(mark)
        try:
            operation()
            job["status"] = "complete"
            record_stage(job, "Complete")
        except Exception as exc:  # noqa: BLE001 - record failures at the worker boundary
            LOG.error(
                "Studio %s failed for %s (%s)", action, folder.name, type(exc).__name__
            )
            job["status"] = "failed"
            message = (
                str(exc)
                if isinstance(exc, (ValueError, FileNotFoundError))
                else type(exc).__name__
            )
            # Provider URLs may contain signed query strings; never export those in errors.
            message = re.sub(
                r"https?://\S+|(?:sk-|cd_)[A-Za-z0-9_-]+", "[source]", message
            )
            job["error"] = message[:240]
            record_stage(job, "Failed")
        finally:
            _STAGE_WRITER.reset(token)
            try:
                job["finished_at"] = timestamp()
                write_json(path, job)
            finally:
                lock.__exit__(None, None, None)

    try:
        mark("Preparing " + action.lower())
        initial = dict(job, stages=list(job["stages"]))
        POOL.submit(work)
    except BaseException:
        lock.__exit__(None, None, None)
        raise
    return initial


def posts_in(folder):
    return [load(path) for path in sorted((folder / "research").glob("*/post.json"))]


def records(obj, *keys):
    if isinstance(obj, list):
        return obj
    for key in keys:
        if isinstance(obj, dict) and isinstance(obj.get(key), list):
            return obj[key]
    return []


def campaign_dir(folder):
    current = load(folder / "selected.json", {})
    return folder / current["directory"] if current.get("directory") else folder


def snapshot(folder):
    current = campaign_dir(folder)
    return {
        "id": folder.name,
        "meta": load(folder / "run.json", {}),
        "brief": load(folder / "brief.json", {}),
        "posts": posts_in(folder),
        "discovery": load(folder / "research/discovery.json", []),
        "patterns": records(load(folder / "research/patterns.json", []), "patterns"),
        "concepts": records(load(folder / "concepts.json", []), "concepts", "slate"),
        "selected": load(folder / "selected.json", {}),
        "creative": load(current / "creative.json", {}),
        "film": load(current / "film.json", {}),
        "locales": {p.stem: load(p) for p in (current / "locales").glob("*.json")},
        "readbacks": load(folder / "readback.json", []),
        "jobs": _jobs(folder),
    }


def db_paths():
    return (
        os.getenv("MARKET_INTEL_DB", "data/market-intel.sqlite3"),
        os.getenv("COMPETITOR_CATALOG_DB", "data/competitor-catalogs.sqlite3"),
    )


def refresh_patterns(folder):
    from market_intel.studio_research import pattern_board

    patterns = pattern_board(posts_in(folder))
    write_json(folder / "research/patterns.json", patterns)
    return patterns


def readback_metrics(values):
    def ratio(top, bottom):
        a, b = values.get(top), values.get(bottom)
        return round(a / b, 5) if a is not None and b is not None and b > 0 else None

    return {
        "hook_rate": ratio("views_3s", "impressions"),
        "hold_rate": ratio("completed_views", "views_3s"),
        "ctr": ratio("clicks", "impressions"),
        "cpa": ratio("spend_inr", "acquisitions"),
    }
