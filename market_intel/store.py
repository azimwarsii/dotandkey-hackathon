"""SQLite persistence for collection and a category-scoped Part 2 report."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from .client import now


SCHEMA = """
CREATE TABLE IF NOT EXISTS product (
    product_ref TEXT PRIMARY KEY, category TEXT COLLATE NOCASE NOT NULL,
    brand TEXT NOT NULL, title TEXT NOT NULL, is_combo INTEGER NOT NULL,
    is_competitor INTEGER NOT NULL, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS product_category ON product(category);
CREATE TABLE IF NOT EXISTS listing (
    product_ref TEXT REFERENCES product, market TEXT, external_id TEXT,
    url TEXT NOT NULL, confidence REAL, data TEXT NOT NULL,
    PRIMARY KEY(product_ref, market, external_id)
);
CREATE TABLE IF NOT EXISTS listing_snapshot (
    product_ref TEXT, market TEXT, external_id TEXT, captured_at TEXT, price REAL, mrp REAL,
    rating REAL, rating_count INTEGER, data TEXT NOT NULL,
    PRIMARY KEY(product_ref, market, external_id, captured_at),
    FOREIGN KEY(product_ref, market, external_id) REFERENCES listing
);
CREATE TABLE IF NOT EXISTS review (
    product_ref TEXT REFERENCES product, body_hash TEXT, source TEXT NOT NULL, body TEXT NOT NULL,
    rating REAL, date TEXT, data TEXT NOT NULL, PRIMARY KEY(product_ref, body_hash)
);
CREATE TABLE IF NOT EXISTS competitor_set (
    category TEXT COLLATE NOCASE, rank INTEGER CHECK(rank BETWEEN 1 AND 5), product_ref TEXT REFERENCES product,
    score REAL NOT NULL, reasons TEXT NOT NULL, PRIMARY KEY(category, rank), UNIQUE(category, product_ref)
);
CREATE TABLE IF NOT EXISTS brand_signal (
    brand TEXT COLLATE NOCASE, captured_at TEXT, data TEXT NOT NULL, PRIMARY KEY(brand, captured_at)
);
CREATE TABLE IF NOT EXISTS news_item (
    brand TEXT COLLATE NOCASE, url TEXT, data TEXT NOT NULL, PRIMARY KEY(brand, url)
);
CREATE TABLE IF NOT EXISTS crawl_log (
    id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, source TEXT NOT NULL,
    status TEXT NOT NULL, credits REAL, detail TEXT
);
"""


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    def log(self, source, status, credits=None, detail=None):
        with self.db:
            self.db.execute("INSERT INTO crawl_log(timestamp,source,status,credits,detail) VALUES(?,?,?,?,?)",
                            (now(), source, status, credits, detail))

    def _product(self, p, competitor):
        self.db.execute("""INSERT INTO product VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(product_ref) DO UPDATE SET category=excluded.category, brand=excluded.brand,
            title=excluded.title, is_combo=excluded.is_combo, is_competitor=excluded.is_competitor,
            data=excluded.data""",
            (p["product_ref"], p["category"], p["brand"], p["title"], bool(p.get("is_combo")),
             competitor, encode(p)))

    def save_product(self, p, competitor=False):
        with self.db:
            self._product(p, competitor)

    def save_catalog(self, products):
        with self.db:
            for product in products:
                self._product(product, False)

    def catalog(self):
        return self._data("SELECT data FROM product WHERE is_competitor=0 ORDER BY category,title")

    def save_selection(self, category, selected):
        with self.db:
            self.db.execute("DELETE FROM competitor_set WHERE category=?", (category,))
            for rank, (p, listing, score, reasons) in enumerate(selected, 1):
                self._product(p, True)
                self._listing(listing)
                self.db.execute("INSERT INTO competitor_set VALUES(?,?,?,?,?)",
                                (category, rank, p["product_ref"], score, encode(reasons)))
                for item in reasons.get("new_arrivals", []):
                    self._news(p["brand"], item)

    def _listing(self, row):
        self.db.execute("""INSERT INTO listing VALUES(?,?,?,?,?,?)
            ON CONFLICT(product_ref,market,external_id) DO UPDATE SET
            url=excluded.url, confidence=excluded.confidence, data=excluded.data""",
            (row["product_ref"], row["market"], row["external_id"], row["url"],
             row.get("confidence"), encode(row)))

    def _reviews(self, reviews):
        for r in reviews:
            normalized = " ".join(r["body"].casefold().split())
            if not normalized:
                continue
            digest = hashlib.sha256(normalized.encode()).hexdigest()
            self.db.execute("INSERT OR IGNORE INTO review VALUES(?,?,?,?,?,?,?)",
                            (r["product_ref"], digest, r["source"], r["body"], r.get("rating"),
                             r.get("date"), encode(r)))

    def save_reviews(self, reviews):
        with self.db:
            self._reviews(reviews)

    def save_listing(self, row, snap=None, reviews=()):
        with self.db:
            self._listing(row)
            if snap:
                stamp = snap["captured_at"]
                data = dict(snap, product_ref=row["product_ref"], market=row["market"],
                            external_id=row["external_id"])
                self.db.execute("""INSERT INTO listing_snapshot VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(product_ref,market,external_id,captured_at) DO UPDATE SET
                    price=coalesce(excluded.price,listing_snapshot.price),
                    mrp=coalesce(excluded.mrp,listing_snapshot.mrp),
                    rating=coalesce(excluded.rating,listing_snapshot.rating),
                    rating_count=coalesce(excluded.rating_count,listing_snapshot.rating_count),
                    data=json_patch(listing_snapshot.data,excluded.data)""",
                                (row["product_ref"], row["market"], row["external_id"], stamp, snap.get("price"),
                                 snap.get("mrp"), snap.get("rating"), snap.get("rating_count"), encode(data)))
            self._reviews(reviews)

    def _news(self, brand, item):
        if item.get("url"):
            self.db.execute("INSERT OR REPLACE INTO news_item VALUES(?,?,?)",
                            (brand, item["url"], encode(dict(item, brand=brand))))

    def save_signals(self, brand, signal, news):
        with self.db:
            if signal:
                stamp = signal.get("captured_at") or now()
                self.db.execute("INSERT OR REPLACE INTO brand_signal VALUES(?,?,?)",
                                (brand, stamp, encode(dict(signal, brand=brand, captured_at=stamp))))
            for item in news:
                self._news(brand, item)

    def _data(self, sql, args=()):
        return [json.loads(row[0]) for row in self.db.execute(sql, args)]

    def report(self, category):
        # Read all tables from one consistent SQLite snapshot during background collection.
        with self.db:
            self.db.execute("BEGIN")
            row = self.db.execute("SELECT category FROM product WHERE category=? AND is_competitor=0 LIMIT 1",
                                  (category,)).fetchone()
            if not row:
                return None
            category = row[0]
            refs = """SELECT product_ref FROM product WHERE category=? AND is_competitor=0
                      UNION SELECT product_ref FROM competitor_set WHERE category=?"""
            args = (category, category)
            def for_products(table, order):
                return self._data(f"SELECT data FROM {table} WHERE product_ref IN ({refs}) ORDER BY {order}", args)
            brands = """SELECT p.brand FROM product p JOIN competitor_set c USING(product_ref) WHERE c.category=?"""
            ranks = [dict(r) for r in self.db.execute("SELECT * FROM competitor_set WHERE category=? ORDER BY rank",
                                                      (category,))]
            for r in ranks:
                r["reasons"] = json.loads(r["reasons"])
            return {"category": category, "products": for_products("product", "is_competitor,title"),
                    "listings": for_products("listing", "product_ref,market,external_id"),
                    "listing_snapshots": for_products("listing_snapshot", "captured_at,product_ref,market"),
                    "reviews": for_products("review", "product_ref,date,body_hash"),
                    "competitor_set": ranks,
                    "brand_signals": self._data(f"SELECT data FROM brand_signal WHERE brand IN ({brands}) ORDER BY brand,captured_at", (category,)),
                    "news_items": [item for item in self._data(f"SELECT data FROM news_item WHERE brand IN ({brands}) ORDER BY brand,url", (category,))
                                   if not item.get("category") or item["category"].casefold() == category.casefold()]}


def report_from(path, category):
    with closing(Store(path)) as store:
        return store.report(category)
