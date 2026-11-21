"use client";
import { dateLabel, withQuery } from "./market-shared";

export function MarketSource({ source }) {
  return (
    <article className="brief-source">
      <small>
        Campaign starting point · {source.category} · {dateLabel(source.as_of)}
      </small>
      <h3>{source.title}</h3>
      {source.href && <a href={source.href}>Open market evidence ↗</a>}
    </article>
  );
}

export default function CampaignBrief({ brief }) {
  const product = brief.product;
  const audience = brief.audience || {};
  const facts = brief.claim_sources || [];
  const claims = [
    ...new Set([
      ...facts
        .filter((r) =>
          ["feature", "benefit", "ingredient", "spf"].includes(r.kind),
        )
        .map((r) => r.text),
      ...(brief.allowed_claims || []),
    ]),
  ];
  const links = (brief.strengths || [])
    .slice(0, 1)
    .concat((brief.gaps || []).slice(0, 1));
  const groups = [
    ["4–5 star product reviews", audience.top_desires],
    ["1–2 star product reviews", audience.top_objections],
    [product.category + " category concerns", audience.category_objections],
  ];
  return (
    <div className="brief-evidence">
      {brief.market_evidence && <MarketSource source={brief.market_evidence} />}
      <div className="brief-columns">
        <section className="panel">
          <h2>What we can say</h2>
          <p>Wording from the Dot &amp; Key product catalog.</p>
          <ul>
            {claims.slice(0, 4).map((claim) => (
              <li key={claim}>{claim}</li>
            ))}
          </ul>
          {claims.length > 4 && (
            <details>
              <summary>{claims.length - 4} more catalog claims</summary>
              <ul>
                {claims.slice(4).map((claim) => (
                  <li key={claim}>{claim}</li>
                ))}
              </ul>
            </details>
          )}
          {!claims.length && (
            <p>No catalog claims recorded for this product.</p>
          )}
          {product.url && (
            <a href={product.url} target="_blank" rel="noreferrer">
              View official product page ↗
            </a>
          )}
        </section>
        <section className="panel">
          <h2>What customers say</h2>
          <p>
            Sampled reviews for campaign planning · {dateLabel(brief.as_of)}
          </p>
          {groups.map(([title, rows]) => (
            <details key={title}>
              <summary>
                {title} ({rows?.length || 0})
              </summary>
              {rows?.length ? (
                rows.map((r) => (
                  <blockquote key={r.id}>
                    “{r.quote}”
                    <footer>
                      {r.rating} / 5 · {r.platform}{" "}
                      {r.source && (
                        <a href={r.source} target="_blank" rel="noreferrer">
                          Read review ↗
                        </a>
                      )}
                    </footer>
                  </blockquote>
                ))
              ) : (
                <p>No sampled quotes in this group.</p>
              )}
            </details>
          ))}
        </section>
      </div>
      {links.length > 0 && (
        <section className="panel brief-market">
          <h2>What stands out in {product.category.toLowerCase()}</h2>
          {links.map((row) => (
            <a
              key={row.id}
              href={
                withQuery("/", {
                  view: "strategy",
                  category: product.category,
                  as_of: brief.as_of,
                }) +
                "#" +
                encodeURIComponent(row.id)
              }
            >
              {row.title} <span aria-hidden="true">↗</span>
            </a>
          ))}
        </section>
      )}
    </div>
  );
}
