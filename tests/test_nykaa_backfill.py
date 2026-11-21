import json

from market_intel.nykaa import _match_all, browse_cards, variant_rows


def _html(state):
    return "<script>window.__PRELOADED_STATE__ = " + json.dumps(state) + ";</script>"


def test_nykaa_sibling_offer_prices_and_review_scope():
    slug = "watermelon-sunscreen/p/100"
    title = "Dot & Key Watermelon Sunscreen SPF 50"
    product = {"name": title, "brandName": "Dot & Key", "id": "100", "parentId": "100", "slug": slug,
               "productType": "configurable", "selectedVariantId":"101", "offerPrice": 150, "mrp": 250,
               "rating": "4.3", "ratingCount": 1200, "reviewCount": 100, "variants": [
                   {"childId":"101", "slug":slug, "name":title, "packSize":"50ml", "offerPrice":150,"mrp":250},
                   {"childId":"102", "slug":slug, "name":title, "packSize":"80ml", "offerPrice":205,"mrp":305}],
               "latestReviews":[{"id":"a","variantId":"101", "description":"Feels light","rating":5},
                                {"id":"b","variantId":"102","description":"Good formula","rating":4},
                                {"id":"c","description":"No variant recorded","rating":3}]}
    url = "https://www.nykaa.com/" + slug
    html = _html({"productPage":{"product":product}})
    variants = variant_rows(html, url, "2026-11-21")
    assert [v["snapshot"]["price"] for v in variants] == [150,205]
    assert all(v["snapshot"]["rating_scope_id"] == "100" and
               v["snapshot"]["rating_scope"] == "parent_product" for v in variants)
    assert [v["reviews"][0]["review_id"] for v in variants] == ["a","b"]
    assert all(len(v["reviews"]) == 1 for v in variants)
    class Offline:
        observations = {url:"2026-11-21"}
    target = {"product_ref":"dk:50","brand":"Dot & Key","title":"Watermelon Sunscreen SPF 50",
              "category":"Sunscreen","size":"80 ml","variants":[{"sku":"dk-80","title":"80ml","available":True}]}
    (match, source), = _match_all(Offline(), [target], variants)
    assert match["external_id"] == "102" and match["url"].endswith("?skuId=102")
    assert source["snapshot"]["mrp"] == 305 and source["snapshot"]["rating_count"] == 1200
    assert not _match_all(Offline(), [dict(target,size="80 g")], variants)
    assert not variant_rows(html, "https://www.nykaa.com/other/p/9999", "2026-11-21")


def test_nykaa_browse_and_simple_review():
    card = {"name":"Gel cleanser","slug":"gel/p/19"}
    assert browse_cards(_html({"categoryListing":{"listingData":{"products":[card],"totalFound":28}}})) == ([card],28)
    search = _html({"searchListingPage":{"listingData":{"products":[card],"totalFound":1}}})
    assert browse_cards(search, search=True) == ([card], 1)
    p = dict(card, id="19", parentId="19", productType="simple", packSize="100ml", brandName="Brand",
             offerPrice=100, latestReviews=[{"description":"Clean skin","isBuyer":False,"likeCount":0}])
    row, = variant_rows(_html({"productPage":{"product":p}}),"https://www.nykaa.com/gel/p/19","2026-11-21")
    assert row["snapshot"]["rating_scope"] == "selected_variant"
    assert row["reviews"][0]["verified"] is False and row["reviews"][0]["helpful_votes"] == 0


def test_peer_net_quantity_overrides_price_denominators():
    from market_intel.competitors import net_quantity, parse_category_page
    card = """<div data-asin="B000000001"><a href="/dp/B000000001"><h2>Example Eye Cream</h2></a>
              <span>Price, product page ₹799 (₹5,327 / 100 ml)</span></div>"""
    listing, = parse_category_page(card, "amazon", "https://www.amazon.in/s?k=eye")
    assert listing["size"] is None
    page = "<div>Net Quantity ‏ : ‎ 15.0 Milliliters</div><script>Net Quantity 100 ml</script>"
    size, proof = net_quantity(page, listing["url"], "2026-11-21")
    assert size == "15 ml" and proof["excerpt"] == "Net Quantity : 15.0 Milliliters"
    assert proof["url"] == listing["url"]
    assert net_quantity(page + "<div>Net Quantity 30 ml</div>", listing["url"]) is None


def test_different_pa_grades_are_not_same_variant():
    from market_intel.nykaa import _same_pa_grade
    assert not _same_pa_grade("SPF 50 PA++++", "SPF 50 PA+++")
    assert _same_pa_grade("SPF50 PA++++ | PA+++", "PA+++")
