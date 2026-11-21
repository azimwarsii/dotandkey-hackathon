"""Action templates keyed to measured SWOT findings or demand gaps."""

from __future__ import annotations

from .swot import make_id

ASPECT_ACTIONS = {
    "white_cast": (
        "Product",
        "Prototype tinted and hybrid-filter finishes. Compare visible cast across skin tones.",
    ),
    "greasy_sticky": (
        "Product",
        "Compare a lighter gel or fluid against the current formula in a wear test.",
    ),
    "breakouts": (
        "Product",
        "Review breakout reports by formulation and batch before commissioning a tolerance study.",
    ),
    "irritation": (
        "Product",
        "Group irritation reports by variant and route recurring patterns to the safety team.",
    ),
    "fragrance": (
        "Product",
        "Test demand for a fragrance-free version against the scented formula.",
    ),
    "hydration": (
        "Product",
        "Run a hydration wear test with the skin types represented in the complaints.",
    ),
    "glow_results": (
        "Product",
        "Compare the advertised result and time frame with the experiences in the cited reviews.",
    ),
    "texture": (
        "Product",
        "Compare spreadability and pilling across sample formulations.",
    ),
    "packaging": (
        "Operations",
        "Test seals, caps and dispensing after transit. Compare a pump or airless pack where appropriate.",
    ),
    "value_price": (
        "Pricing",
        "Test a trial size and show the price per unit next to each pack size.",
    ),
    "authenticity": (
        "Marketplace",
        "Audit sellers and seals on the cited channels and identify the official storefront in listing copy.",
    ),
    "spf_protection": (
        "Product",
        "Review the protection claims and rated evidence with the testing team before changing SPF messaging.",
    ),
    "longevity": (
        "Product",
        "Test wear duration and check whether the usage directions match the tested routine.",
    ),
    "under_makeup": (
        "Product",
        "Test the formula under common foundation and primer formats.",
    ),
    "absorption": (
        "Product",
        "Measure absorption time in a side-by-side application test.",
    ),
    "cleansing": (
        "Product",
        "Compare removal of sunscreen and makeup in a repeatable cleansing test.",
    ),
    "barrier_repair": (
        "Product",
        "Check whether the barrier-support claim matches substantiated outcomes and the targeted skin type.",
    ),
    "pigmentation": (
        "Product",
        "Audit the claimed time to visible change and the evidence supporting it.",
    ),
}


def build_recommendations(swot, gaps, trends):
    actions = []
    seen = set()

    def add(kind, action, evidence_id, threshold, subject):
        key = kind, action, subject
        if key in seen:
            next(r for r in actions if r["id"] == make_id(*key))["trigger_ids"].append(
                evidence_id
            )
            return
        seen.add(key)
        actions.append(
            {
                "id": make_id(*key),
                "type": kind,
                "subject": subject,
                "action": action,
                "trigger_ids": [evidence_id],
                "trigger_threshold": threshold,
            }
        )

    for quadrant in swot.values():
        for row in quadrant:
            rule, subject, data = row["rule"], row["subject"], row["metric_values"]
            args = row["id"], row["threshold"], subject
            if (
                rule in {"complaint_lift", "aspect_disadvantage"}
                and subject in ASPECT_ACTIONS
            ):
                add(*ASPECT_ACTIONS[subject], *args)
            elif rule == "channel_gap":
                add(
                    "Marketplace",
                    f"Audit the {data['lower_market']} listing, seller mix and review themes for this SKU. Compare with {data['higher_market']}.",
                    *args,
                )
            elif rule == "premium_price":
                add(
                    "Pricing",
                    "Test a smaller trial pack or a value pack against the current price per unit.",
                    *args,
                )
            elif rule == "messaging_advantage":
                add(
                    "Messaging",
                    f"Test a message about {subject.replace('_', ' ')} using the cited customer language. Substantiate any comparison before publication.",
                    *args,
                )
            elif rule == "peer_pain":
                add(
                    "Product",
                    f"Interview customers about {subject.replace('_', ' ')} before defining a prototype.",
                    *args,
                )
            elif rule == "missing_trend":
                add(
                    "Assortment",
                    f"Test a {data['term']} line extension with category shoppers.",
                    *args,
                )
            elif rule == "recent_launch":
                add(
                    "Assortment",
                    f"Compare the new {subject} listings with the closest Dot & Key variants before the next assortment review.",
                    *args,
                )
            elif rule == "better_value":
                add(
                    "Pricing",
                    f"Benchmark the comparable pack against {data['competitor']} before the next price test.",
                    *args,
                )
            elif rule in {"discount_pressure", "storefront_discount"}:
                add(
                    "Pricing",
                    "Track the competitor promotion across the next price observations before changing the regular price.",
                    *args,
                )
            elif rule == "brand_momentum":
                add(
                    "Competitive research",
                    f"Review channel expansion by {data['brand']} alongside its reported quarterly growth.",
                    *args,
                )
            elif rule in {"top_rating", "value_leader"}:
                add(
                    "Merchandising",
                    "Test showing the observed rating or unit value with its source, count and date on the product page.",
                    *args,
                )
    for row in gaps.get("whitespace", [])[:5]:
        values = (
            row.get("attributes")
            or row.get("metric_values", {}).get("attributes")
            or {}
        )
        spec = (
            ", ".join(str(v) for v in values.values() if v is not None)
            if isinstance(values, dict)
            else str(values)
        )
        add(
            "Assortment",
            "Test demand for a concept matching " + (spec or row["title"]) + ".",
            row["id"],
            row["threshold"],
            row["title"],
        )
    for row in gaps.get("unmet_needs", [])[:3]:
        add(
            "Customer research",
            "Validate this recurring request with category shoppers before prototyping.",
            row["id"],
            row["threshold"],
            row["title"],
        )
    for row in trends.get("trending", []):
        if row["missing_at_dot_key"] and not any(
            a["subject"] == row["term"] for a in actions
        ):
            add(
                "Assortment",
                f"Test a {row['term']} concept in this category.",
                row.get("id", row["term"]),
                "Two independent term-growth signals ≥ 1.5",
                row["term"],
            )
    return actions
