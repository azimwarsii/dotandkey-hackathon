"""Count generation requests in a shared, short-lived SQLite window."""

import hashlib
import ipaddress
import os
import sqlite3
import time
from contextlib import closing

from starlette.responses import JSONResponse

from . import runs

OPERATIONS = {
    "brief",
    "concepts",
    "generate",
    "discover",
    "deconstruct",
    "localize",
    "film",
    "readback",
    "uploads",
}


def is_generation(path):
    return path in {"/api/ask", "/api/refresh", "/studio/runs"} or (
        path.startswith("/studio/runs/") and path.rsplit("/", 1)[-1] in OPERATIONS
    )


def allowed(identity, limit=60):
    root = runs.root().parent
    root.mkdir(parents=True, exist_ok=True)
    now = time.time()
    key = hashlib.sha256(identity.encode()).hexdigest()
    with closing(sqlite3.connect(root / "rate-limits.sqlite3", timeout=10)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS requests (client TEXT, at REAL)")
        db.execute("CREATE INDEX IF NOT EXISTS request_time ON requests(at)")
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM requests WHERE at <= ?", (now - 3600,))
        count = db.execute(
            "SELECT COUNT(*) FROM requests WHERE client=?", (key,)
        ).fetchone()[0]
        if count >= limit:
            return False
        db.execute("INSERT INTO requests VALUES (?,?)", (key, now))
        return True


class GenerationThrottle:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and is_generation(scope["path"])
        ):
            from starlette.concurrency import run_in_threadpool

            host = (scope.get("client") or ("unknown",))[0]
            if os.getenv("STUDIO_TRUST_PROXY") == "1":
                forwarded = dict(scope["headers"]).get(b"x-real-ip", b"")
                try:
                    host = str(ipaddress.ip_address(forwarded.decode("ascii")))
                except ValueError:
                    pass
            if not await run_in_threadpool(allowed, host):
                response = JSONResponse(
                    {"detail": "Hourly generation limit reached. Try again later."},
                    status_code=429,
                    headers={"Retry-After": "3600"},
                )
                return await response(scope, receive, send)
        return await self.app(scope, receive, send)
