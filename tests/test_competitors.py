from datetime import datetime, timedelta, timezone
from html import escape
import json

from market_intel.competitors import collect_signals, parse_category_page, select_competitors


def listing(label, i, *, count=100, price=325):
    title = label + " Sunscreen - SPF 50"
    url = f"/item-{i}/p/itm{i}?pid=SNR{i}"
    return f'''<div data-id="SNR{i}"><a href="{url}" title="{escape(title)}">{escape(title)}</a>
        <span>50 g</span><span id="productRating_{i}">4.1</span><span>({count:,})</span>
        <div>₹{price}</div></div>'''


def test_amazon_card_evidence_and_canonical_page():
    html = '''<div data-asin="B000000001"><a href="/any/dp/B000000001?ref=x">
        <h2>Plum Vitamin C Sunscreen 50 ml</h2></a><div class="a-price">
        <span class="a-offscreen">₹349.00</span></div><span aria-label="1.2K ratings"></span></div>'''
    row, = parse_category_page(html, "amazon", "https://www.amazon.in/s?k=sunscreen")
    assert (row["price"], row["rating_count"], row["size"]) == (349.0, 1200, "50 ml")
    assert row["url"] == "https://www.amazon.in/dp/B000000001"


def test_json_ld_retains_unseeded_brand_and_missing_fields():
    data = {"@type": "ItemList", "itemListElement": [{"@type": "ListItem",
        "item": {"@type": "Product", "name": "Hydrating serum",
                 "brand": {"name": "Independent Labs"},
                 "url": "https://www.amazon.in/dp/B000000002"}}]}
    html = '<script type="application/ld+json">' + json.dumps(data) + '</script>'
    row, = parse_category_page(html, "amazon", "https://www.amazon.in/s?k=serum")
    assert row["brand"] == "Independent Labs"
    assert row["price"] is None and row["rating_count"] is None


class CategoryClient:
    has_crustdata = True

    def __init__(self):
        self.urls = []

    def enrich(self, urls):
        self.urls.extend(urls)
        pages = {}
        for url in urls:
            if "/p/" in url:
                product = {"@type": "Product", "brand": {"name": "Independent Labs"}}
                pages[url] = '<script type="application/ld+json">' + json.dumps(product) + '</script>'
            elif "amazon.in" in url:
                pages[url] = "<title>Request blocked</title>"
            elif "recency_desc" in url:
                pages[url] = listing("Independent Labs", 100)
            elif "page=1" in url:
                names = ["Dot & Key", "Independent Labs", "Plum", "PLUM", "Mamaearth", "Foxtale"]
                pages[url] = "".join(listing(v, i) for i, v in enumerate(names))
            else:
                pages[url] = listing("Aqualogica", 200) + listing("Foxtale combo", 201)
        return pages

    def search(self, query, **kwargs):
        if kwargs["sources"] == ["ai"]:
            return [{"source":"ai","content":"Independent Labs and Foxtale", "references":[
                {"url":"https://example.org/article", "title":"Independent Labs sunscreen review", "snippet":"A tested formula."}]}]
        return []


def test_ranking_filters_brands_combines_pages_and_preserves_evidence():
    client = CategoryClient()
    selected = select_competitors(client, "Sunscreen", [
        {"category": "Sunscreen", "title": "SPF 50 sunscreen", "price": 400, "brand": "Dot & Key"},
        {"category": "Sunscreen", "title": "Combo", "price": 10, "is_combo": True}])
    names = [p["brand"] for p, _, _, _ in selected]
    assert names == ["Independent Labs", "Plum", "Mamaearth", "Foxtale", "Aqualogica"]
    independent, listing_row, score, reasons = selected[0]
    assert reasons["target_price_band"] == [400, 400]
    assert listing_row["product_ref"] == independent["product_ref"]
    assert not reasons["seed_brand"] and reasons["ai_crosscheck"]
    assert reasons["new_arrivals"][0]["event_type"] == "marketplace_new_arrival"
    assert reasons["new_arrivals"][0]["date"] is None
    assert reasons["position"] == 2 and reasons["rating_count"] == 100
    assert abs(score - sum(v * reasons["weights"][k] for k, v in reasons["components"].items())) < 1e-12
    assert selected[-1][3]["position"] == 7
    assert sum("page=2" in url for url in client.urls) == 2


class SignalClient:
    has_crustdata = True

    def company(self, domain):
        assert domain == "foxtale.in"
        return {"web_traffic": {"quarterly_growth": 0.15}, "headcount": None}

    def search(self, query, **kwargs):
        today = datetime.now(timezone.utc).date()
        assert kwargs["sources"] == ["news"]
        assert datetime.fromtimestamp(kwargs["start_date"], timezone.utc).date() == today - timedelta(days=90)
        news = {"title": "Foxtale launches a new sunscreen", "date": today.isoformat(),
                "url": "https://example.org/foxtale-news"}
        return [news, news.copy(), {**news, "url": "https://example.org/stale", "date": "2020-01-01"},
                {**news, "title": "An unrelated launch", "url": "https://example.org/unrelated"}]


def test_company_and_recent_news():
    signal, news = collect_signals(SignalClient(), "FOXTALE")
    assert signal["domain"] == "foxtale.in" and signal["web_traffic"]["quarterly_growth"] == 0.15
    assert len(news) == 1 and news[0]["event_type"] == "launch_mention"


def test_missing_credentials_can_return_public_news_without_company_data():
    class Public:
        has_crustdata = False

        def get(self, url):
            if "/products.json?" in url:
                return "<html>not a Shopify storefront</html>"
            assert url.startswith("https://news.google.com/rss/search?")
            return """<rss><channel><item><title>Foxtale launches SPF</title>
                <link>https://example.org/news</link><source>Publisher</source></item></channel></rss>"""
    signal, news = collect_signals(Public(), "Foxtale")
    assert signal is None and news[0]["publisher"] == "Publisher"
    assert news[0]["source"] == "google_news_rss"


def test_unseeded_brand_in_unstructured_title_is_verified_from_pdp():
    class Unseeded(CategoryClient):
        has_crustdata = False

        def enrich(self, urls):
            pages = {}
            for url in urls:
                if "/p/" in url:
                    product = {"@type": "Product", "name": "Independent Super Serum SPF 50",
                               "brand": {"@type": "Brand", "name": "Independent Super"}}
                    pages[url] = '<script type="application/ld+json">' + json.dumps(product) + '</script>'
                elif "flipkart" in url:
                    pages[url] = '<div data-id="S1"><a title="Independent Super Serum SPF 50" href="/one/p/itmabc?pid=S1">Serum</a></div>'
            return pages
    (product, listing_row, _, reasons), = select_competitors(
        Unseeded(), "Serum", [{"category": "Serum", "title": "SPF 50 Serum", "price": 349}])
    assert product["brand"] == "Independent Super" and reasons["brand_source"] == listing_row["url"]


def test_common_word_brand_news_requires_beauty_context():
    class Ambiguous:
        has_crustdata = True

        def get(self, url):
            return "{}"

        def company(self, domain):
            return {}

        def search(self, *args, **kwargs):
            return [{"title": "Pilgrim travel news", "url": "https://example.org/1"},
                    {"title": "Pilgrim launches beauty collection", "url": "https://example.org/2"}]
    assert [item["title"] for item in collect_signals(Ambiguous(), "Pilgrim")[1]] == ["Pilgrim launches beauty collection"]


def test_public_storefront_signal_preserves_publication_evidence():
    today = datetime.now(timezone.utc).date().isoformat()

    class PublicShop:
        has_crustdata = False

        def get(self, url):
            if "news.google.com" in url:
                return "<rss/>"
            return json.dumps({"products": [
                {"id": 123, "title": "Face serum", "handle": "serum", "published_at": today},
                {"id": 456, "title": "Retired serum", "handle": "retired", "published_at": "2018-10-11"}]})
    signal, _ = collect_signals(PublicShop(), "Foxtale")
    assert signal["source"] == "shopify_storefront" and signal["sample_size"] == 2
    assert signal["recent_storefront_publications"] == [
        {"id": 123, "title": "Face serum", "published_at": today, "url": "https://foxtale.in/products/serum"}]


def test_amazon_brand_heading_and_sponsored_link():
    html = """
    <div data-asin="B000000001"><h2>DOT &amp; KEY</h2>
        <a href="/sspa/click"><h2>Vitamin C + E Super Bright Sunscreen 80 g</h2></a></div>"""
    row, = parse_category_page(html, "amazon", "https://www.amazon.in/s?k=spf")
    assert row["brand"] == "DOT & KEY" and row["title"].endswith("Sunscreen 80 g")
    assert row["url"] == "https://www.amazon.in/dp/B000000001"


def test_selected_size_ignores_alternate_pack_sizes():
    from market_intel.competitors import _selected_size
    page = '<div><div>Selected Quantity:</div><div>800 ml</div></div><div>200 ml</div>'
    assert _selected_size(page, "flipkart") == "800 ml"


def test_dove_news_distinguishes_singer_from_personal_care_brand():
    from market_intel.competitors import matches_news_brand
    assert not matches_news_brand("Dove", "Curology and Dove Cameron create skincare line")
    assert matches_news_brand("Dove", "Dove launches skincare-inspired body serums")


def test_company_record_exports_aggregates_and_verified_domain_news_only():
    from market_intel.competitors import _company_signal
    raw = {"basic_info":{"name":"Foxtale", "primary_domain":"foxtale.in", "contact_email":"private@example.test"},
           "funding":{"phone_number":"private", "investors_detailed":[{"private":"field"}],"last_round_amount_usd":100},
           "news":[{"private":"field"}], "unrequested_people":[{"private":"field"}],
           "web_traffic":{"domain_traffic":{"www.foxtale.in":{"qoq_pct":22.1, "monthly_visitors":80},
                                            "another.example":{"qoq_pct":90}}},
           "hiring":{"openings_count":7, "recent_titles_csv":"excluded"}}
    saved = _company_signal(raw,"Foxtale","foxtale.in","2026-11-21")
    assert saved["entity_name"] == "Foxtale" and saved["hiring"] == {"openings_count":7}
    assert saved["funding"] == {"last_round_amount_usd":100}
    assert saved["web_traffic"] == {"domain_traffic":{"foxtale.in":{"monthly_visitors":80,"qoq_pct":22.1}}}
    assert "private" not in json.dumps(saved) and "news" not in saved
    assert _company_signal(raw,"A Different Brand","other.test","2026-11-21") is None
