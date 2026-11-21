"""Public, single-origin market API for the Market Studio web app."""

# ruff: noqa: UP045 -- FastAPI evaluates these annotations on Python 3.9.

import os
from datetime import date
from secrets import compare_digest
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import ask, cache, catalog, jobs, market

router = APIRouter(prefix="/api", tags=["market studio"])
STREAM_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}


def checked(day):
    if day and not 1900 <= day.year <= 9998:
        raise HTTPException(422, "Analysis date is outside the supported range")
    return day


@router.get("/health")
def health():
    with cache.database() as db:
        present = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='product'"
        ).fetchone()
    if not present:
        raise HTTPException(503, "Market database is unavailable")
    return {"status": "ok"}


@router.get("/version")
def version():
    return {
        "version": "1.0",
        "revision": os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("APP_REVISION"),
    }


@router.get("/category/{category}/insights")
def category_insights(category: str, as_of: Optional[date] = None):
    return cache.report_for(category, checked(as_of))


@router.get("/overview")
def overview(
    category: str = "Sunscreen",
    as_of: Optional[date] = None,
    compare: Optional[date] = None,
):
    return market.overview(category, checked(as_of), checked(compare))


@router.get("/products")
def list_products(
    category: Optional[str] = None,
    q: str = Query("", max_length=180),
    as_of: Optional[date] = None,
):
    return catalog.products(category, q, checked(as_of))


@router.get("/products/{handle}")
def product(handle: str, as_of: Optional[date] = None):
    return catalog.product_detail(handle, checked(as_of))


@router.get("/competitors")
def competitors(category: str = "Sunscreen", as_of: Optional[date] = None):
    return catalog.competitors(category, checked(as_of))


@router.get("/launches")
def launches(category: str = "Sunscreen", as_of: Optional[date] = None):
    report = cache.report_for(category, checked(as_of))
    return {
        "category": report["category"],
        "as_of": report["as_of"],
        "launches": catalog.launches(report),
    }


class Question(BaseModel):
    category: str = Field(default="Sunscreen", min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=1500)
    as_of: Optional[date] = None


@router.post("/ask")
def answer(body: Question):
    if not body.question.strip():
        raise HTTPException(422, "Enter a market question")
    report = cache.report_for(body.category, checked(body.as_of))
    return StreamingResponse(
        ask.answer(body.question, report),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )


@router.post("/refresh", status_code=202)
def refresh(category: str = "Sunscreen"):
    return jobs.submit("refresh", cache.category_name(category))


@router.post("/jobs/nightly", status_code=202)
def nightly(authorization: Optional[str] = Header(default=None)):
    token = os.getenv("JOBS_CRON_TOKEN")
    if not token or not compare_digest(
        (authorization or "").encode(), ("Bearer " + token).encode()
    ):
        raise HTTPException(403, "Private maintenance endpoint")
    return jobs.submit("nightly")


@router.get("/jobs/{job_id}")
def job(job_id: str):
    return jobs.status(*jobs.job_path(job_id))


@router.get("/jobs/{job_id}/events")
def job_events(job_id: str, last_event_id: int = Header(default=0, ge=0)):
    path, root = jobs.job_path(job_id)
    return StreamingResponse(
        jobs.events(path, root, last_event_id),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )
