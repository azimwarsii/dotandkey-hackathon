"""Single-flight market collection with durable status and shared Studio SSE progress."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException

from market_intel.studio import runs

from .ask import event
from .cache import directory, read_json, save, warm

LOG = logging.getLogger(__name__)
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="market-jobs")
TERMINAL = {"complete", "failed", "interrupted"}


def folder():
    return directory().parent / "jobs"


def prune_old_runs():
    cutoff = time.time() - 14 * 86400
    for meta in runs.root().glob("*/run.json"):
        path = meta.parent
        if path.name == runs.DEMO or path.is_symlink():
            continue
        try:
            with runs.locked(path):
                # Use recorded activity as well as file timestamps. A just-completed
                # operation may have touched only its job document inside a subfolder.
                state = runs.load(meta, {})
                if state.get("pinned") or meta.stat().st_mtime >= cutoff:
                    continue
                if any(
                    p.is_file() and p.name != ".lock" and p.stat().st_mtime >= cutoff
                    for p in path.rglob("*")
                ):
                    continue
                tomb = path.parent.parent / (".pruned-" + uuid4().hex)
                path.rename(tomb)
            shutil.rmtree(tomb)
        except (FileNotFoundError, runs.Busy):
            continue


def collect(kind, category, stage):
    from market_intel.__main__ import crawl
    from market_intel.catalog_history import IST, snapshot_asins, snapshot_catalogs
    from market_intel.client import Client
    from market_intel.store import Store

    db, catalog = runs.db_paths()
    partial = False
    deadline = time.monotonic() + max(
        1, float(os.getenv("MARKET_COLLECTION_TIMEOUT_SECONDS", "7200"))
    )
    with (
        closing(Store(db)) as store,
        closing(
            Client(str(directory().parent), store.log, refresh=True, deadline=deadline)
        ) as client,
    ):
        if kind == "nightly":
            stage("Snapshotting competitor storefronts")
            day = datetime.now(IST).date()
            result = snapshot_catalogs(client, catalog, day)
            partial = bool(result["errors"])
            stage("Snapshotting marketplace search pages")
            snapshot_asins(client, catalog, day)
        else:
            args = Namespace(
                category=category,
                stage="all",
                overrides=None,
                judgeme_pages=2,
                reddit_threads=1,
                review_pages=2,
            )
            crawl(client, store, args, progress=stage)
    # The product catalog changes across categories even for category-scoped crawls.
    warm(stage)
    if kind == "nightly":
        stage("Pruning expired campaign runs")
        prune_old_runs()
    if partial:
        raise ValueError(
            "Some storefronts were unavailable. Available snapshots and dashboards were updated."
        )


def submit(kind, category=None):
    root = folder()
    root.mkdir(parents=True, exist_ok=True)
    lock = runs.locked(root)
    try:
        lock.__enter__()
    except runs.Busy:
        active = read_json(root / "active.json")
        if active and active["kind"] == kind and active.get("category") == category:
            job = read_json(root / (active["id"] + ".json"))
            if job and job["status"] not in TERMINAL:
                return job
        raise HTTPException(409, "Market collection is already running")
    job = {
        "id": uuid4().hex,
        "kind": kind,
        "category": category,
        "action": "Nightly market update"
        if kind == "nightly"
        else "Refresh " + category,
        "status": "running",
        "stage": "Starting collection",
        "created_at": runs.timestamp(),
    }
    runs.record_stage(job, "Starting collection")
    path = root / (job["id"] + ".json")

    def progress(stage):
        runs.record_stage(job, stage)
        save(path, job)

    def work():
        try:
            collect(kind, category, progress)
            job.update(status="complete")
            runs.record_stage(job, "Complete")
        except Exception as exc:  # noqa: BLE001 - retain durable failure state at the worker boundary
            LOG.error(
                "Market %s failed during %s (%s)",
                kind,
                job["stage"],
                type(exc).__name__,
            )
            job.update(
                status="failed",
                error=f"Market update stopped during {job['stage'].lower()}.",
            )
            if isinstance(exc, TimeoutError):
                job["error"] = (
                    "Market collection reached its time limit. Previously collected observations are available."
                )
            if isinstance(exc, ValueError) and str(exc).startswith("Some storefronts"):
                job["error"] = str(exc)
            runs.record_stage(job, "Failed")
        finally:
            try:
                job["finished_at"] = runs.timestamp()
                save(path, job)
            finally:
                lock.__exit__(None, None, None)

    try:
        save(path, job)
        save(root / "active.json", {k: job[k] for k in ("kind", "category", "id")})
        initial = dict(job, stages=list(job["stages"]))
        POOL.submit(work)
        return initial
    except BaseException:
        lock.__exit__(None, None, None)
        raise


def job_path(job_id):
    # Studio jobs and market jobs both use uuid4().hex.
    if len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id):
        raise HTTPException(404, "Unknown job")
    file = folder() / (job_id + ".json")
    if file.exists():
        return file, file.parent
    for path in runs.root().glob("*/jobs/" + job_id + ".json"):
        return path, path.parent.parent
    raise HTTPException(404, "Unknown job")


def status(path, lock_root):
    job = read_json(path)
    if not job:
        raise HTTPException(404, "Unknown job")
    if job["status"] not in TERMINAL:
        try:
            with runs.locked(lock_root):
                job = read_json(path)
                if job and job["status"] not in TERMINAL:
                    job.update(
                        status="interrupted",
                        error="The worker stopped before completion.",
                    )
                    runs.record_stage(job, "Interrupted")
                    save(path, job)
        except runs.Busy:
            pass
    return {**job, "stage": job.get("stage", job["action"])}


async def events(path, lock_root, cursor=0):
    last = None
    idle = 0
    while True:
        job = await asyncio.to_thread(status, path, lock_root)
        history = job.get("stages", [])
        if history:
            # Replay fast stages skipped between polls. EventSource resumes with
            # Last-Event-ID on reconnect. Old Studio jobs have no stage history.
            for i, state in enumerate(history[cursor:], cursor + 1):
                public = {
                    k: v
                    for k, v in job.items()
                    if k not in ("stages", "finished_at", "error")
                }
                public.update(state)
                if state["status"] in TERMINAL:
                    public.update(
                        {k: job[k] for k in ("finished_at", "error") if k in job}
                    )
                yield f"id: {i}\n" + event(public)
                cursor = i
                idle = 0
        elif job != last:
            yield event(job)
            idle = 0
        last = job
        if job["status"] in TERMINAL:
            return
        if idle == 20:
            yield ": keepalive\n\n"
            idle = 0
        await asyncio.sleep(0.5)
        idle += 1


if __name__ == "__main__":
    job = submit("nightly")
    path, root = job_path(job["id"])
    while True:
        snapshot = status(path, root)
        if snapshot["status"] in TERMINAL:
            print(snapshot["stage"], flush=True)
            raise SystemExit(0 if snapshot["status"] == "complete" else 1)
        time.sleep(2)
