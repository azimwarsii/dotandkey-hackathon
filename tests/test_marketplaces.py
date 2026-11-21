import json
import unittest
from unittest.mock import Mock

from market_intel.marketplaces import canonical_listing, collect_listings, discover, listing_match_is_valid, parse_listing


class MarketplaceTests(unittest.TestCase):
    def test_canonical_urls_preserve_variant_and_reject_other_sites(self):
        self.assertEqual(canonical_listing("amazon", "https://www.amazon.in/x/dp/B0DVLMD36J/ref=abc"),
                         ("B0DVLMD36J", "https://www.amazon.in/dp/B0DVLMD36J"))
        self.assertEqual(canonical_listing("nykaa", "https://www.nykaa.com/test/p/123?src=one&skuId=44"),
                         ("44", "https://www.nykaa.com/test/p/123?skuId=44"))
        self.assertEqual(canonical_listing("flipkart", "https://www.flipkart.com/name/p/itmA9?pid=ABC&lid=2"),
                         ("ABC", "https://www.flipkart.com/name/p/itmA9?pid=ABC"))
        self.assertIsNone(canonical_listing("amazon", "https://www.amazon.in.other.test/dp/B0DVLMD36J"))

    def test_discovery_rejects_variants_and_wrong_brands(self):
        client = Mock(has_crustdata=True, observations={})
        product = dict(title="Mango Detan Gel Sunscreen SPF 50", product_ref="dk:test", size="80 g", brand="Dot & Key")
        text = "Dot & Key Mango Detan Gel Sunscreen SPF 50 80 g"
        titles = [text.replace("80 g", "50 g"), text.replace("80 g", "80 ml"), text.replace("SPF 50", "SPF 40"),
                  text.replace("Dot & Key", "Example"), text + " (Pack of 2)", text + " Stick", text]
        client.search.return_value = [dict(title=t, url=f"https://www.amazon.in/dp/B0TEST000{i}") for i,t in enumerate(titles)]
        listing = discover(client, product, "amazon")
        self.assertEqual(listing["external_id"], "B0TEST0006")
        client.search.return_value = client.search.return_value[:-1]
        self.assertIsNone(discover(client, product, "amazon"))

    def test_competitor_multipacks_and_mixed_products(self):
        for brand, product, candidate, size in [
            ("mCaffeine", "Sweet Escape Perfume Body Lotion", "By the Blues Body Lotion & Sweet Escape Body Lotion 300mlx2", "300 ml"),
            ("Parachute", "Coco Nourish Body Lotion", "Coco Nourish Body Lotion 400 ml & Cocoa repair Body Lotion 250 ml", "400 ml"),
            ("Cetaphil", "Gentle Skin Cleanser Face Wash", "Oily Skin Cleanser | Daily Face Wash | 118ml", "118 ml"),
            ("Dot & Key", "Hair Mask with Moringa & Argan Oil", "Moringa & Argan Hair Fall Shampoo 200ml", "200 ml"),
            ("Dot & Key", "Cica Niacinamide Oil-Free Moisturizer", "Watermelon Gel Moisturizer With Niacinamide 60g", "60 g"),
            ("Dot & Key", "Mango Gel Face Wash", "Mango Gel Face Wash+Mango Gel Sunscreen SPF 50 50ml", "50 ml"),
        ]:
            p = dict(product_ref="competitor:ref", title=product, size=size, brand=brand)
            l = dict(product_ref="competitor:ref", market="amazon", url="https://www.amazon.in/dp/B0TEST0000",
                     external_id="B0TEST0000", title=candidate, brand=brand)
            with self.subTest(candidate=candidate):
                self.assertFalse(listing_match_is_valid(p, l))

    def test_variants_and_unit_price_do_not_establish_pack_size(self):
        p = dict(product_ref="dk:ref", brand="Dot & Key", title="Meltie Lip Balm", variants=[{"title":"Cocoa Crème"}])
        l = dict(product_ref="dk:ref", brand="Dot & Key", market="amazon", url="https://www.amazon.in/dp/B0TEST0000",
                 external_id="B0TEST0000", title="Meltie Lip Balm Berry Crumble")
        self.assertFalse(listing_match_is_valid(p, l))
        l["title"] = "Meltie Lip Balm Cocoa Creme"
        self.assertTrue(listing_match_is_valid(p, l))
        p["size"] = l["size"] = "100 g"
        l["snippet"] = "Meltie Lip Balm Cocoa Creme 4.2 out of 5 stars Price, product page ₹149 (₹149 /100 g)"
        self.assertFalse(listing_match_is_valid(p, l))

    def test_separate_observation_for_search_card_price(self):
        url = "https://www.amazon.in/dp/B0TEST0000"
        client = Mock(has_crustdata=False, observations={url:"pdp-time"}, has_extractor=False)
        client.enrich.return_value = {url:'<span id="acrCustomerReviewText">400 ratings</span>'}
        listing = dict(product_ref="dk:ref", market="amazon", url=url, card_price=199,
                       source_url="https://www.amazon.in/s?k=test", discovered_at="search-time")
        first, second = list(collect_listings(client, [listing]))
        self.assertNotIn("price", first[1])
        self.assertEqual(second[1], {"price":199, "source":"marketplace_search_card",
                                     "url":listing["source_url"], "captured_at":"search-time"})

    def test_flipkart_embedded_product_and_review_metadata(self):
        product = {"@type": "Product", "offers": {"price": 399, "priceCurrency": "INR"},
                   "aggregateRating": {"ratingValue": 4.3, "ratingCount": 99, "reviewCount": 22}}
        state = {"multiWidgetState": {"pageDataResponse": {"pageContext": {"fdpEventTracking": {"events": {
            "psi": {"ppd": {"mrp": 500}, "pr": {"individualRatingsCount": [{"ratingValue": 5, "ratingCount": 10}]}}}}}},
            "widgetsData": {"slots": [{"value": {"type": "ProductReviewValue", "text": "My dry skin feels softer",
                "rating": 5, "reviewPropertyMap": {"VERIFIED_PURCHASE": True}, "helpfulCount": 0,
                "productAttributeList": [{"name":"Quantity", "value":"50 g"}]}}]}}}
        html = f'<script>window.__INITIAL_STATE__ = {json.dumps(state)};</script><script type="application/ld+json">{json.dumps(product)}</script>'
        snap, rows = parse_listing("flipkart", html, "ref")
        self.assertEqual((snap["price"],snap["mrp"],snap["rating"],snap["rating_count"],snap["rating_histogram"]), (399,500,4.3,99,{"5":10}))
        self.assertEqual((rows[0]["verified"], rows[0]["helpful_votes"], rows[0]["skin_type"],rows[0]["reviewed_variant"]["Quantity"]), (True,0,"dry","50 g"))

    def test_amazon_reviews_summary_and_rank(self):
        html = ('<span id="acrPopover" title="4.5 out of 5 stars"></span><span id="acrCustomerReviewText">1,234 ratings</span>'
                '<div data-hook="cr-insights-ai-generated-feedback">People mention texture.</div>'
                '<div data-hook="cr-insights-aspect-button"><span class="a-text-bold">Texture</span></div>'
                '<table><tr><td>Best Sellers Rank</td><td>#12 in Beauty #2 in Sunscreen</td></tr></table>'
                '<div data-hook="review"><span data-hook="review-body">Works for me.</span><a data-hook="avp-badge">Verified Purchase</a>'
                '<i data-hook="review-star-rating">4.0 out of 5 stars</i><span data-hook="helpful-vote-statement">One person found this helpful</span></div>')
        snap, rows = parse_listing("amazon", html, "ref")
        self.assertEqual((snap["rating_count"],snap["bsr"],snap["aspect_chips"]), (1234,12,["Texture"]))
        self.assertEqual(snap["category_ranks"][1],dict(rank=2,category="Sunscreen"))
        self.assertEqual((rows[0]["verified"],rows[0]["helpful_votes"],rows[0]["rating"]), (True,1,4.0))

    def test_nykaa_retry_and_cached_timestamp(self):
        url = "https://www.nykaa.com/item/p/123"
        state = {"props": {"pageProps": {"product": {"name":"Item","rating":4.1,"discountedPrice": 300, "mrp":400}}}}
        html = f'<script id="__NEXT_DATA__">{json.dumps(state)}</script>'
        client = Mock(has_crustdata=True, observations={url:"2026-11-21T08:00:00Z"}, has_extractor=False)
        client.enrich.side_effect = [{url:'<title>Access Denied</title>'},{url:html}]
        listing = dict(market="nykaa",product_ref="ref",url=url)
        _, snapshot, _ = next(collect_listings(client,[listing]))
        self.assertEqual((snapshot["source"],snapshot["price"],snapshot["mrp"],snapshot["captured_at"]),
                         ("pdp",300,400,"2026-11-21T08:00:00Z"))
        client.enrich.assert_called_with([url], human_mode=True)

    def test_blocked_listing_uses_only_attributable_snippet_metrics(self):
        client = Mock(has_crustdata=True, observations={}, has_extractor=False)
        client.enrich.return_value = {}
        listing = dict(market="amazon", product_ref="ref", url="https://www.amazon.in/dp/B0TEST0000",
                       snippet="₹349, 4.4 out of 5 (1,123 ratings)", discovered_at="old")
        _, snap, reviews = next(collect_listings(client,[listing]))
        self.assertEqual((snap["source"], snap["rating_count"],snap["price"],snap["captured_at"],reviews),
                         ("search_snippet", 1123,349,"old",[]))
        client.extract.assert_not_called()

    def test_schema_fallback_fills_gaps_without_overwriting_observed_values(self):
        url = "https://www.nykaa.com/test/p/7"
        client = Mock(has_crustdata=False, observations={}, has_extractor=True)
        client.enrich.return_value = {url:'<main>Price Rs 600</main><script type="application/ld+json">{"@type":"Product","aggregateRating":{"ratingValue":4.5}}</script>'}
        client.extract.return_value = {"price": 600, "rating": 3.0}
        listing = dict(market="nykaa",product_ref="ref",url=url)
        _, snap, _ = next(collect_listings(client,[listing]))
        self.assertEqual((snap["price"],snap["rating"],snap["llm_fields"]), (600,4.5,["price"]))


if __name__ == "__main__":
    unittest.main()


def test_flipkart_rendered_review_keeps_observed_variant_and_date_precision():
    from market_intel.marketplace_parsers import parse_listing

    page = """<div><div><div dir="auto">5.0</div><div dir="auto">•</div>
    <div dir="auto">Simply awesome</div></div><div dir="auto">Review for: Quantity 80 g</div>
    <div dir="auto">No visible white cast.</div><div><div dir="auto">Helpful for 1K</div>
    <div dir="auto">Verified Purchase</div><div dir="auto"> · Apr, 2024</div></div></div>"""
    _, rows = parse_listing("flipkart", page, "product")
    row, = rows
    assert (row["body"], row["rating"], row["verified"]) == ("No visible white cast.", 5, True)
    assert (row["reviewed_variant"], row["date"], row["date_text"]) == ("Quantity 80 g", None, "Apr, 2024")
    assert row["helpful_votes"] is None
