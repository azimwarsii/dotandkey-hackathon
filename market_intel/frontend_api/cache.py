"""Versioned, atomically published insight reports and their smaller dashboard indexes."""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
from contextlib import closing, contextmanager
from datetime import date, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

from fastapi import HTTPException

from market_intel.catalog_history import latest_snapshot_date
from market_intel.insights import build_insights
from market_intel.studio.runs import db_paths

SCHEMA = 2
MAX_CATEGORY_DATES = 12


def directory():
    return Path(
        os.getenv(
            "MARKET_INSIGHT_CACHE", str(Path(db_paths()[0]).parent / "cache/insights")
        )
    )


@contextmanager
def database():
    path = Path(db_paths()[0]).resolve()
    if not path.is_file():
        raise HTTPException(503, "Market database is unavailable")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        yield db


def categories():
    with database() as db:
        return [
            row[0]
            for row in db.execute(
                "SELECT DISTINCT category FROM product WHERE is_competitor=0 AND is_combo=0 ORDER BY category"
            )
        ]


def category_name(value):
    for name in categories():
        if name.casefold() == value.strip().casefold():
            return name
    raise HTTPException(404, "Unknown market category")


def latest_day():
    with database() as db:
        market = db.execute(
            "SELECT max(date(captured_at)) FROM listing_snapshot"
        ).fetchone()[0]
        history = latest_snapshot_date(db_paths()[1])
        dates = [str(day) for day in (market, history) if day]
        if not dates:
            dates = [
                day
                for (day,) in db.execute("""
                SELECT max(date(json_extract(data,'$.published_at'))) FROM product
                UNION ALL SELECT max(date(date)) FROM review
                UNION ALL SELECT max(date(json_extract(data,'$.observed_at'))) FROM review
                UNION ALL SELECT max(date(captured_at)) FROM brand_signal
            """)
                if day
            ]
    return date.fromisoformat(max(dates)) if dates else date.today()


def signature():
    # Inserts may still be in SQLite's WAL while another reader holds a snapshot.
    stamps = [SCHEMA]
    for source in db_paths():
        path = Path(source).resolve()
        stamps.append(str(path))
        for target in (path, Path(str(path) + "-wal")):
            try:
                stat = target.stat()
                stamps.extend(
                    (stat.st_mtime_ns, stat.st_size) if stat.st_size else (0, 0)
                )
            except FileNotFoundError:
                stamps.extend((0, 0))
    return stamps


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        try:
            json.dump(
                obj, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            )
            f.flush()
            os.replace(f.name, path)
        finally:
            Path(f.name).unlink(missing_ok=True)


def opportunity(report):
    f = report["forecast"]
    return {
        "category": report["category"],
        "opportunity_score": f["opportunity_score"],
        "forecast_growth": f["forecast_growth"],
        "dk_share": f["score_factors"]["dk_share"],
        "as_of": report["as_of"],
    }


def cache_paths(name, day):
    stem = quote(name.casefold(), safe="") + "-" + day.isoformat()
    root = directory()
    return root / (stem + ".json"), root / (stem + ".index.json")


def read_json(path):
    try:
        return json.loads(path.read_bytes())
    except (FileNotFoundError, ValueError):
        return None


def cached_report(name, day, *, index_only=False):
    path, index = cache_paths(name, day)
    root = path.parent
    root.mkdir(parents=True, exist_ok=True)
    slug = quote(name.casefold(), safe="")

    def hit(source):
        meta = read_json(index)
        if meta and meta.get("source") == source and path.is_file():
            return meta["opportunity"] if index_only else read_json(path)
        return None

    # The category lock covers both files and eviction across all web workers.
    # Readers can share it, and different categories can rebuild independently.
    with (root / ("." + slug + ".lock")).open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        source = signature()
        data = hit(source)
        if data is not None:
            return data
        fcntl.flock(lock, fcntl.LOCK_EX)
        source = signature()
        data = hit(source)
        if data is not None:
            return data
        report = build_insights(*db_paths(), name, day)
        if report is None:
            raise HTTPException(404, "No insight report for this category")
        row = opportunity(report)
        save(path, report)
        save(index, {"source": source, "opportunity": row})
        indexes = sorted(
            root.glob(slug + "-*.index.json"), key=lambda p: p.stat().st_mtime_ns
        )
        if len(indexes) > MAX_CATEGORY_DATES:
            current = latest_day()
            keep = {
                index,
                cache_paths(name, current)[1],
                cache_paths(name, current - timedelta(days=30))[1],
            }
            excess = [p for p in indexes if p not in keep][
                : len(indexes) - MAX_CATEGORY_DATES
            ]
            for item in excess:
                item.unlink(missing_ok=True)
                item.with_suffix("").with_suffix(".json").unlink(missing_ok=True)
        return row if index_only else report


def report_for(category, day=None):
    return cached_report(category_name(category), day or latest_day())


def warm(progress=lambda stage: None):
    from .market import overview

    day = latest_day()
    names = categories()
    for name in names:
        progress("Indexing " + name)
        cached_report(name, day)
    for name in names:
        progress("Preparing " + name + " dashboard")
        overview(name, day)


if __name__ == "__main__":
    warm(print)
