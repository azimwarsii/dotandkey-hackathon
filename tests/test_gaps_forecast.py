from datetime import date
import unittest

from market_intel.attributes import attributes, category_for
from market_intel.forecast import build_forecast
from market_intel.gaps import build_gaps

DAY = date(2026,11,21)


def product(ref, brand, title, price=375):
    return {"product_ref":ref,"brand":brand,"title":title,"price":price,"category":"Sunscreen"}


def review(ref, i, text, month=8, source="flipkart"):
    return {"product_ref":ref,"source":source,"date":f"2026-{month:02d}-01","body":f"{text} Review {month}-{i}.",
            "review_id":f"{ref}-{i}-{month}","url":"https://example.test/" + ref,"rating":3}


class GapForecastTests(unittest.TestCase):
    def test_attributes(self):
        self.assertEqual(category_for({"title":"Lip Balm SPF 50 With Sunscreen"}),"Lip Balm")
        fields = attributes({"title":"Tinted Sunscreen Stick SPF50+ PA++++ for Oily Skin",
                             "ingredients":["Niacinamide"],"price":"499","size":"20 g"})
        self.assertEqual(fields["spf"],50)
        self.assertEqual(fields["pa"],"PA++++")
        self.assertEqual(fields["formats"],["stick","tinted"])
        self.assertIn("niacinamide",fields["ingredients"])
        self.assertEqual(fields["price_band"],"under ₹500")

    def test_gap_requires_observed_neighbor_demand_or_repeated_request(self):
        raw = {"category":"Sunscreen","products":[product("a","Dot & Key","Gel Sunscreen",350),
                       product("b","Peer","Cream Sunscreen",650)],"competitor_set":[{"product_ref":"b"}],
               "reviews":[review("a",i,"Liked the gel.") for i in range(20)] + [review("b",i,"Cream application.") for i in range(20)]}
        gaps = build_gaps(raw,{}, {},DAY)
        row = next(x for x in gaps["whitespace"] if x["attributes"]=={"formats":"gel","price_band":"₹500–999"})
        self.assertEqual(row["metric_values"]["suppliers"],0)
        self.assertEqual(row["n"],40)
        self.assertEqual(set(e["product_ref"] for e in row["evidence"]),{"a","b"})
        raw["reviews"] = [review("a",1,"The gel works. I wish it came as a stick."),
                         review("b",2,"Please make a larger pack."),review("b",3,"I wish it came in a bigger bottle.")]
        gaps = build_gaps(raw,{}, {},DAY)
        self.assertFalse(gaps["whitespace"])
        self.assertEqual(gaps["unmet_needs"][0]["theme"],"larger pack")
        self.assertEqual(gaps["unmet_needs"][0]["n"],2)

    def test_negative_pain_requires_eligible_own_and_four_peer_brands(self):
        brands = ["Dot & Key","A","B","C","D","E"]
        products = [product(str(i),b,"Gel Sunscreen") for i,b in enumerate(brands)]
        rows = {"category":"Sunscreen","products":products,"competitor_set":[{"product_ref":p["product_ref"]} for p in products[1:]],"reviews":[]}
        metrics = {"brands":{b:{"aspects":{"texture":{"claim_eligible":True,"nss":-0.5,"directional_n":36,
                     "evidence":[{"quote":"I disliked the texture.","polarity":"neg"}]}}} for b in brands}}
        self.assertEqual(build_gaps(rows,metrics,{},DAY)["category_pain"][0]["n"],216)
        metrics["brands"]["Dot & Key"]["aspects"]["texture"]["claim_eligible"]=False
        self.assertFalse(build_gaps(rows,metrics,{},DAY)["category_pain"])

    def test_forecast_excludes_unshared_first_party_sources_and_partial_month(self):
        products = [product(str(i),brand,"Gel Sunscreen") for i,brand in enumerate(["Dot & Key","A","B","C","D","E"])]
        reviews = [review(p["product_ref"],i,"Observed customer review",m) for p in products for m in range(5,11) for i in range(m-4)]
        raw = {"category":"Sunscreen","products":products,"competitor_set":[{"product_ref":p["product_ref"]} for p in products[1:]],"reviews":reviews}
        gaps = {"whitespace":[{"id":"cell"}]}
        before = build_forecast(raw,{},gaps,DAY)
        raw["reviews"] += [review("0",i,"First party sample",9,"judgeme") for i in range(90)]
        raw["reviews"].append(review("0",456,"Partial month",11))
        after = build_forecast(raw,{},gaps,DAY)
        self.assertEqual(before["opportunity_score"], after["opportunity_score"])
        self.assertEqual(after["score_factors"]["dk_share"],round(1/6,5))
        self.assertEqual(len(after["projection"]),3)
        self.assertGreater(after["forecast_growth"],0)
        self.assertEqual(after["status"],"sample_projection")
        self.assertEqual(after["series"][-1]["month"],"2026-10")
        raw["reviews"]=[]
        self.assertIsNone(build_forecast(raw,{},gaps,DAY)["opportunity_score"])

    def test_cumulative_review_counts_take_precedence_and_deduplicate_history(self):
        products = [product(str(i),b,"Gel Sunscreen") for i,b in enumerate(["Dot & Key","A","B","C","D","E"])]
        raw = {"category":"Sunscreen","products":products,"competitor_set":[{"product_ref":p["product_ref"]} for p in products[1:]],
               "reviews":[], "listing_snapshots":[{"product_ref":p["product_ref"],"external_id":p["product_ref"],"market":"flipkart",
                   "captured_at":f"2026-11-{day}","review_count":10 if day=="05" else 20, "rating_count":90000}
                   for p in products for day in ("05","20")]}
        factors = build_forecast(raw,{}, {},DAY)["score_factors"]
        self.assertEqual((factors["share_source"],factors["dk_review_volume"],factors["top_six_review_volume"]),
                         ("listing_review_counts",20,120))

    def test_cross_market_all_time_share_counts_one_source_per_product(self):
        products = [product(str(i),b,"Gel Sunscreen") for i,b in enumerate(["Dot & Key","A","B","C","D","E"])]
        rows = [review(str(i), i, "Reviewed on channel",8,"amazon" if i in (0,5) else "flipkart") for i in range(6)]
        rows.append(review("0",7,"Reviewed on another channel",8,"flipkart"))
        for r in rows:
            r["date"]="2023-05-01"
        raw={"category":"Sunscreen","products":products,"competitor_set":[{"product_ref":p["product_ref"]} for p in products[1:]],"reviews":rows}
        groups={"category_pain":[{"id":"pain","aspect":"fragrance"}],"unmet_needs":[{"id":"wish","theme":"fragrance"}]}
        factors=build_forecast(raw,{},groups,DAY)["score_factors"]
        self.assertEqual((factors["share_source"],factors["dk_review_volume"],factors["top_six_review_volume"]),
                         ("one_marketplace_per_product_sample",1,6))
        self.assertEqual(factors["gap_count"],1)

    def test_rating_increments_need_a_stable_panel_and_never_sum_with_reviews(self):
        products = [product("a","Dot & Key","Gel Sunscreen"), product("b","Peer","Cream Sunscreen")]
        raw={"category":"Sunscreen","products":products,"competitor_set":[{"product_ref":"b"}],"reviews":[],
             "listing_snapshots":[{"product_ref":r,"market":"amazon","external_id":r,"rating_count":m*40,
                      "captured_at":f"2026-{m:02d}-01","source":"pdp"} for r in ("a","b") for m in range(4,12)]}
        result = build_forecast(raw,{}, {},DAY)
        self.assertIn("same-listing",result["source"])
        self.assertEqual(result["series"][-1]["rating_increment"],80)
        self.assertEqual(result["projection"][0]["index"],100.0)
        self.assertIsNone(result["opportunity_score"])


if __name__ == "__main__":
    unittest.main()


def test_unmet_needs_exclude_recommendations_and_satisfied_searches():
    from market_intel.gaps import _wish_matches

    for body in ("I was looking for a hydrating gel and this one worked perfectly.",
                 "If you're looking for a good everyday sunscreen, I highly recommend this.",
                 "You only need a pea-sized amount."):
        assert not list(_wish_matches(body))
    assert list(_wish_matches("I'm still looking for a fragrance-free stick."))
    assert list(_wish_matches("I need a larger pack."))
