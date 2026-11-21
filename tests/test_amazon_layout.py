from market_intel.marketplaces import parse_listing


def test_current_amazon_pdp_excludes_brand_summary_and_review_controls():
    html = """
    <div class="brand-snapshot-box-section">Customers say this brand is great</div>
    <div id="corePrice_feature_div">
      <span class="apex-pricetopay-value"><span class="a-offscreen">₹476.00</span></span>
    </div>
    <div data-csa-c-slot-id="cr-product-insights-detail-page">
      <span data-testid="overall-summary">Customers mention quick absorption.</span>
      <span data-testid="aspect-label">Absorption (10)</span>
    </div>
    <div data-hook="review" id="R123">
      <h5 data-hook="reviewTitle">Good texture</h5>
      <div data-hook="reviewText">Brief content visible
        <div data-hook="reviewRichContentContainer">Absorbs quickly</div>Read more
      </div><a data-hook="format-strip">Size: 80 ml</a>
    </div>
    """
    snapshot, reviews = parse_listing("amazon", html, "p")
    assert snapshot["customers_say"] == "Customers mention quick absorption."
    assert snapshot["aspect_chips"] == ["Absorption (10)"]
    assert snapshot["price"] == 476
    assert len(reviews) == 1
    assert reviews[0]["body"] == "Absorbs quickly"
    assert reviews[0]["title"] == "Good texture"
    assert reviews[0]["reviewed_variant"] == "Size: 80 ml"


def test_absolute_review_date_is_normalized_and_relative_text_is_preserved():
    import json

    rows = [{"reviewBody": stamp, "datePublished": stamp} for stamp in ("7 May 2026", "6 months ago")]
    markup = '<script type="application/ld+json">' + json.dumps({"@type":"Product","review":rows}) + "</script>"
    _, reviews = parse_listing("flipkart", markup, "p")
    assert reviews[0]["date"] == "2026-05-07"
    assert reviews[1]["date"] is None and reviews[1]["date_text"] == "6 months ago"
