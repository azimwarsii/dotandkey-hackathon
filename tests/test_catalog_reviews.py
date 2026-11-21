import json

from market_intel.catalog import collect_catalog
from market_intel.reviews import collect_judgeme, collect_reddit


def test_catalog_paginates_and_links_single_skus_to_bundles():
    products = [
        {"id": 1, "handle": "gel", "title": "Gel SPF 50+", "product_type": "Sunscreen",
         "tags": ["fltr_ingredients_Cica", "fltr_skin_concern_Acne", "fltr_skin_type_Oily"],
         "body_html": "<p>Net quantity</p><script>ignore</script>",
         "variants": [{"id": 2, "title": "50ml", "sku": "DK_GEL", "price": "99", "available": True}]},
        {"id": 3, "handle": "duo", "title": "Gel Duo", "product_type": "combo",
         "variants": [{"id": 4, "title": "100ml", "sku": "DK_GEL_2", "price": "150"}]},
        {"id": 5, "handle": "gift", "title": "Sample", "product_type": "Free"},
    ]

    class Client:
        def get(self, url, params):
            return json.dumps({"products": products[:1] if params["page"] == 1 else
                               products[1:] if params["page"] == 2 else []})

        def extract(self, schema, text):
            assert set(schema["properties"]) == {"hero_ingredient"}
            return {"hero_ingredient": "Cica"}

    gel, duo = collect_catalog(Client())
    assert gel["description"] == "Net quantity"
    assert (gel["size"], gel["price"], gel["spf"]) == ("50 ml", 99, "50+")
    assert gel["hero_ingredient"] == "Cica"
    assert duo["component_refs"] == [gel["product_ref"]]


def test_judgeme_excludes_group_reviews_and_repeated_bodies():
    product = {"brand": "Dot & Key", "product_ref": "dk:5", "id": 5, "handle": "gel", "url": "https://example.com/products/gel"}
    own = {"product_url": "/products/gel", "body_html": "<p>Good.</p>", "rating": 4,
           "verified_buyer": False, "thumb_up": 0, "cf_answers": [{"question_title": "Skin Type", "value": "Oily"}]}

    class Client:
        def get(self, url, params):
            assert params["page"] <= 2
            rows = [dict(own, product_url="/products/other"), own] if params["page"] == 1 else [own]
            return json.dumps({"product_external_id": 5, "pagination": {"total_pages": 2}, "reviews": rows})

    rows = collect_judgeme(Client(), product, pages=5)
    assert len(rows) == 1
    assert (rows[0]["body"], rows[0]["skin_type"], rows[0]["verified"], rows[0]["helpful_votes"]) == ("Good.", "Oily", False, 0)


def test_reddit_only_keeps_product_mentions_in_roundups():
    product = {"product_ref": "dk:5", "brand": "Dot & Key", "category": "Sunscreen", "title": "Watermelon Sunscreen SPF 50"}
    post = {"title": "My sunscreen roundup", "permalink": "/r/example/comments/123/",
            "selftext": "Reviews below", "created_utc": 1000}
    comments = [{"body": "The Dot and Key watermelon sunscreen felt light on my oily skin.", "score": 3,
                 "created_utc": 1001, "replies": ""},
                {"body": "Which cleanser?", "replies": ""}]

    class Client:
        def search(self, query, site):
            return [{"url": "https://www.reddit.com/r/example/comments/123/a_title/"},
                    {"url": "https://www.reddit.com.fake.example/r/example/comments/abc"}]

        def get(self, url, params):
            assert url == "https://old.reddit.com/r/example/comments/123.json"
            return json.dumps([{"data": {"children": [{"kind": "t3", "data": post}]}},
                               {"data": {"children": [{"kind": "t1", "data": c} for c in comments]}}])

    rows = collect_reddit(Client(), product)
    assert len(rows) == 1
    assert rows[0]["reddit_score"] == 3
    assert rows[0]["rating"] is None and rows[0]["helpful_votes"] is None


def test_judgeme_retains_good_first_page_after_block_or_malformed_response():
    product = {"brand": "Dot & Key", "id": 5, "product_ref": "dk:5", "handle": "gel", "url": "https://example.com/products/gel"}

    class Client:
        def __init__(self, bad):
            self.bad = bad
            self.log_entries = []

        def get(self, url, params):
            if params["page"] == 1:
                return json.dumps({"product_external_id": 5, "reviews": [{"body_html": "<p>Good</p>"}],
                                   "pagination": {"total_pages": 2}})
            return self.bad

        def log(self, source, status, detail):
            self.log_entries.append(status)

    for bad in ["<html>Rate limited</html>", '{"reviews":[]}', '{"product_external_id":5,"reviews":{}}',
                '{"product_external_id":5,"reviews":[],"pagination":{"total_pages":null}}']:
        client = Client(bad)
        assert [r["body"] for r in collect_judgeme(client, product, 2)] == ["Good"]
        assert client.log_entries == ["partial_reviews"]


def test_pdp_net_quantity_for_known_shade_does_not_leak_into_new_pack():
    from market_intel.catalog import _normalize

    raw = {"id": 1, "title": "Plushie", "handle": "plushie-jelly-lip-balm", "product_type": "Lip Balm",
           "options": [{"name": "Color"}], "variants": [
               {"id": 2, "title": "Toffee Melt", "sku": "DK_LBPJ", "available": True, "grams": 4},
               {"id": 3, "title": "New shade", "sku": "DK_NEW"},
               {"id": 4, "title": "Berry Kiss 20g", "sku": "DK_LBBK"},
           ]}
    item = _normalize(raw)
    assert [v["size"] for v in item["variants"]] == ["10 g", None, "20 g"]
    assert item["size_source"]["url"] == "https://www.dotandkey.com/products/plushie-jelly-lip-balm"
    assert item["size_source"]["field"] == "Net Qty"
    raw["options"].append({"name": "Pack size"})
    assert _normalize(raw)["size"] is None
