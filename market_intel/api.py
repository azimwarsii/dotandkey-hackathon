import os
from datetime import date
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from .insights import build_insights, opportunity_overview
from .store import report_from
from .studio.api import router as studio_router

load_dotenv()
app = FastAPI(title="Dot & Key market intelligence", version="1")


@app.get("/category/{c}/report-data")
def report_data(c: str):
    report = report_from(os.getenv("MARKET_INTEL_DB", "data/market-intel.sqlite3"), c)
    if report is None:
        raise HTTPException(status_code=404, detail="Unknown category")
    return report


@app.get("/category/{c}/insights")
def category_insights(c: str, as_of: Optional[date] = None):
    report = build_insights(
        os.getenv("MARKET_INTEL_DB", "data/market-intel.sqlite3"),
        os.getenv("COMPETITOR_CATALOG_DB", "data/competitor-catalogs.sqlite3"),
        c,
        as_of,
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Category has no insight report")
    return report


@app.get("/insights/opportunities")
def opportunities(as_of: Optional[date] = None):
    return opportunity_overview(
        os.getenv("MARKET_INTEL_DB", "data/market-intel.sqlite3"),
        os.getenv("COMPETITOR_CATALOG_DB", "data/competitor-catalogs.sqlite3"),
        as_of,
    )


app.include_router(studio_router)
