"""Contract, retry and replay tests across transport, SQLite and Part 2."""
import json
from contextlib import closing

import httpx
import pytest
from fastapi.testclient import TestClient

from market_intel.api import app
from market_intel.client import Client
from market_intel.store import Store


def test_transport_cache_out_of_order_and_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("CRUSTDATA_API_KEY", "test-key")
    sleeps = []
    monkeypatch.setattr("market_intel.client.time.sleep", sleeps.append)
    calls = []
    def route(req):
        assert req.headers["x-api-version"] == "2025-11-01"
        assert req.headers["authorization"] == "Bearer test-key"
        payload = json.loads(req.content)
        calls.append(payload)
        if len(calls) == 1:
            return httpx.Response(429, headers={"x-ratelimit-reset": "2"})
        urls = payload["urls"]
        assert len(urls) <= 10
        return httpx.Response(200, json=[{"url": u, "timestamp": 1700000000, "success": True, "content": u}
                                         for u in reversed(urls)], headers={"x-credits-used": str(len(urls))})
    logs = []
    urls = [f"https://example.org/{i}" for i in range(12)]
    with closing(Client(tmp_path, lambda *a, **k: logs.append((a,k)), transport=httpx.MockTransport(route))) as c:
        assert c.enrich(urls) == {u:u for u in urls}
        assert c.enrich(urls[:3]) == {u:u for u in urls[:3]}
        assert c.observations[urls[0]].startswith("2023-11-14")
    assert len(calls) == 3
    assert 2 in sleeps
    assert logs[-1][1]["credits"] == "2"


def test_keyed_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("CRUSTDATA_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    def route(req):
        body = json.loads(req.content)
        if req.url.path.endswith("/search/live"):
            assert body["site"] == "amazon.in" and body["sources"] == ["web"]
            data = {"success": True, "results": [{"url":"https://example.org/", "title":"Example"}]}
        elif req.url.path == "/company/enrich":
            data = [{"matches": [{"confidence_score": 1.0, "company_data": {"headcount": {"total": 8}}}]}]
        else:
            assert req.headers["x-api-key"] == "test-key"
            data = {"content":[{"type":"tool_use","name":"extract_fields","input":{"size":"50g"}}]}
        return httpx.Response(200, json=data)
    with closing(Client(tmp_path, lambda *a, **k: None, transport=httpx.MockTransport(route))) as c:
        assert c.search("test", site="amazon.in")[0]["title"] == "Example"
        assert c.company("example.org")["headcount"]["total"] == 8
        assert c.extract({"type":"object","properties":{"size":{"type":"string"}}}, "size 50g")["size"] == "50g"


def test_category_report_history_atomic_rank_and_review_dedup(tmp_path, monkeypatch):
    path = tmp_path / "test.sqlite"
    monkeypatch.setenv("MARKET_INTEL_DB", str(path))
    with closing(Store(path)) as store:
        product = {"product_ref":"p", "title":"Sunscreen", "category":"Sunscreen","brand":"Dot & Key"}
        store.save_product(product)
        store.save_product(dict(product, product_ref="other", category="Serum"))
        l = {"product_ref":"p","market":"amazon","external_id":"id","url":"https://example.com/p"}
        review = {"source":"amazon","product_ref":"p","body":"Good texture","rating":5}
        store.save_listing(l, {"captured_at":"2026-01-01", "price":100}, [review])
        store.save_listing(l, {"captured_at":"2026-01-01", "price":100}, [dict(review, body="good   Texture")])
        store.save_listing(l, {"captured_at":"2026-02-01", "price":90})
        rival = dict(product, product_ref="r", brand="Example")
        entry = (rival, dict(l, product_ref="r"), .8, {"new_arrivals":[]})
        store.save_selection("Sunscreen", [entry])
        with pytest.raises(Exception, match="UNIQUE"):
            store.save_selection("Sunscreen", [entry, entry])
        store.save_signals("Example", {"headcount":10}, [{"url":"https://news.example/a","title":"Launch"}])
    response = TestClient(app).get("/category/sunscreen/report-data")
    assert response.status_code == 200
    body = response.json()
    assert [p["product_ref"] for p in body["products"]] == ["p","r"]
    assert [s["price"] for s in body["listing_snapshots"]] == [100, 90]
    assert len(body["reviews"]) == len(body["competitor_set"]) == len(body["news_items"]) == 1
    assert body["brand_signals"][0]["brand"] == "Example"
    assert TestClient(app).get("/category/missing/report-data").status_code == 404


def test_full_cli_crawl_with_keyed_providers_and_cached_replay(tmp_path, monkeypatch):
    """Exercise all six stages against representative provider response shapes."""
    from market_intel import __main__ as cli

    monkeypatch.setenv("CRUSTDATA_API_KEY", "fixture")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(Client, "_pace", lambda *args: None)
    source = {"id": 3, "title": "Mango Sunscreen", "handle": "mango", "product_type": "Sunscreen",
              "variants": [{"id": 4, "title": "50 g", "price": "399", "available": True}]}
    rival_card = ('<div data-asin="B000000001"><a href="/dp/B000000001"><h2>Plum Sunscreen 50 g</h2>'
                  '</a><span>₹349</span><span aria-label="800 ratings"></span></div>')
    markup = '<script type="application/ld+json">' + json.dumps({
        "@type": "Product", "name": "Sunscreen", "offers": {"price": 349, "priceCurrency": "INR"},
        "review": {"reviewBody": "Works well", "reviewRating": {"ratingValue": 5}}
    }) + "</script>"
    thread_url = "https://www.reddit.com/r/IndianSkincareAddicts/comments/abc/test/"
    def route(request):
        url = request.url
        payload = json.loads(request.content) if request.content else {}
        if url.path == "/products.json":
            data = {"products": [source] if url.params["page"] == "1" else []}
        elif "judge.me" in url.host:
            data = {"product_external_id": 3, "reviews": [{"body": "Light feel", "rating": 4}],
                    "pagination": {"total_pages": 1}}
        elif url.path == "/account/endpoints":
            data = {"endpoints": [{"path": "/company/enrich", "status": "enabled",
                                   "fields": {"enabled": ["headcount.total"]}}]}
        elif url.path == "/web/enrich/live":
            data = [{"url": u, "success": True, "timestamp": 1700000000,
                     "content": rival_card if "amazon.in/s?" in u else markup}
                    for u in payload["urls"]]
        elif url.path == "/web/search/live":
            hits = []
            if payload["sources"] == ["ai"]:
                hits = [{"source":"ai", "content":"Plum is a competitor", "references":[
                    {"url":"https://example.org/ranking", "title":"Plum sunscreen comparison", "snippet":"Includes Plum."}]}]
            elif payload["sources"] == ["news"]:
                hits = [{"title":"Plum unveils skincare collection", "url":"https://example.org/news"}]
            elif payload.get("site") == "reddit.com" and "Mango" in payload["query"]:
                hits = [{"url": thread_url}]
            elif payload.get("site") == "amazon.in" and "Mango" in payload["query"]:
                hits = [{"title":"Dot & Key Mango Sunscreen 50 g", "url":"https://www.amazon.in/dp/B000000002"}]
            data = {"success": True, "results": hits}
        elif url.host == "old.reddit.com":
            post = {"permalink":"/r/IndianSkincareAddicts/comments/abc/test/", "title":"Dot & Key Mango Sunscreen",
                    "selftext":"I have dry skin and tried this for a week."}
            data = [{"data":{"children":[{"data":post}]}}, {"data":{"children":[]}}]
        elif url.path == "/company/enrich":
            assert payload["fields"] == ["headcount"]
            data = [{"matches":[{"confidence_score":1.0, "company_data":{"headcount":{"total":12}}}]}]
        else:
            raise AssertionError(str(url))
        return httpx.Response(200, json=data, headers={"x-credits-used":"1"})
    monkeypatch.setattr(cli, "Client", lambda *args, **kw: Client(*args, **kw, transport=httpx.MockTransport(route)))
    db = tmp_path / "run.sqlite"
    argv = ["--db", str(db), "--cache", str(tmp_path / "cache"), "crawl", "--category", "Sunscreen"]
    cli.main(argv)
    cli.main(argv)
    with closing(Store(db)) as store:
        report = store.report("Sunscreen")
        assert [r["rank"] for r in report["competitor_set"]] == [1]
        assert report["competitor_set"][0]["reasons"]["ai_crosscheck"]
        assert len(report["listing_snapshots"]) == 2
        assert {r["source"] for r in report["reviews"]} == {"judgeme", "amazon", "reddit"}
        assert report["brand_signals"][0]["headcount"]["total"] == 12
        assert any(n["event_type"] == "launch_mention" for n in report["news_items"])


def test_insufficient_credits_switches_same_fetch_to_public(tmp_path, monkeypatch):
    monkeypatch.setenv("CRUSTDATA_API_KEY", "test")
    calls = []
    def route(req):
        calls.append(req.url.host)
        if req.url.host == "api.crustdata.com":
            return httpx.Response(402)
        return httpx.Response(200, text="<main>Observed listing</main>")
    url = "https://example.org/product"
    with closing(Client(tmp_path, lambda *args, **kw: None, transport=httpx.MockTransport(route))) as c:
        assert c.enrich([url])[url] == "<main>Observed listing</main>"
        assert not c.has_crustdata
        assert calls == ["api.crustdata.com", "example.org"]


def test_distinct_catalog_products_cannot_share_one_ambiguous_marketplace_variant():
    from market_intel.marketplaces import resolve_listing_conflicts

    exact = {"market":"flipkart","external_id":"F1","product_ref":"milk","confidence":0.895,
             "match_method":"marketplace_search"}
    near = dict(exact, product_ref="rice-water", confidence=0.813)
    other = dict(near, external_id="F2")
    assert resolve_listing_conflicts([near,exact,other]) == [exact,other]
    assert resolve_listing_conflicts([near,dict(exact,confidence=0.813)]) == []


def test_openrouter_extraction_uses_named_tool_and_cached_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    calls = []
    def route(request):
        calls.append(request.url)
        assert request.url.host == "openrouter.ai"
        assert request.headers["authorization"] == "Bearer fixture-openrouter"
        body = json.loads(request.content)
        assert body["model"] == "test/model"
        assert body["tool_choice"]["function"]["name"] == "extract_fields"
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [
            {"function": {"name": "extract_fields", "arguments": '{"size":"50 g","other":1}'}}]}}]})
    with closing(Client(tmp_path, lambda *a, **kw: None, transport=httpx.MockTransport(route))) as c:
        for _ in range(2):
            assert c.extract({"properties": {"size": {"type": "string"}}}, "Tube 50 g") == {"size": "50 g"}
    assert len(calls) == 1


def test_company_selects_domain_match_and_rejects_same_score_ambiguity(tmp_path, monkeypatch):
    monkeypatch.setenv("CRUSTDATA_API_KEY","test")
    def entry(domain, score, name):
        return {"confidence_score":score, "company_data":{"basic_info":{"name":name,"primary_domain":domain,
                "contact_email":"private@example.test"},"funding":{"phone_number":"private","num_funding_rounds":1}}}
    def route(req):
        target = json.loads(req.content)["domains"][0]
        matches = [entry("unrelated.test",1.0,"Unrelated"),entry(target,.95,"Actual brand")]
        if target == "ambiguous.test":
            matches.append(entry(target,.95,"Different operator"))
        return httpx.Response(200,json=[{"matched_on":target,"match_type":"domain","matches":matches}])
    with closing(Client(tmp_path,lambda *a,**kw:None,transport=httpx.MockTransport(route))) as c:
        actual = c.company("brand.test")
        assert actual["basic_info"] == {"name":"Actual brand","primary_domain":"brand.test"}
        assert actual["funding"] == {"num_funding_rounds":1}
        assert not c.company("ambiguous.test")
