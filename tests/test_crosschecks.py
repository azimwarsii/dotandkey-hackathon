from market_intel.crosschecks import cited_brand_matches


def test_only_named_citations_attach_to_existing_brand():
    results = [{"source":"ai", "content":"Foxtale and Deconstruct are competitors.", "references":[
        {"url":"https://example.org/sun", "title":"Deconstruct gel sunscreen", "snippet":"A category comparison."},
        {"url":"https://example.org/misc", "title":"Other Indian brands"}]}]
    assert not cited_brand_matches("Foxtale","query","date", results)
    row, = cited_brand_matches("Deconstruct", "query", "date",results)
    assert row["url"] == "https://example.org/sun"
    assert row["source"] == "crustdata_ai_reference"
    assert row["observed_at"] == "date"
