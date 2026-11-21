"use client";
import { useEffect, useState } from "react";
import {
  Mark,
  Facts,
  label,
  dateLabel,
  price,
  number,
  percent,
  withQuery,
  useMarketData,
  Status,
} from "./market-shared";
import { StepChart } from "./market-charts";

const array = (x) => (Array.isArray(x) ? x : []);
const titleOf = (x) =>
  x?.title ||
  x?.action ||
  x?.term ||
  x?.need ||
  x?.text ||
  x?.aspect ||
  "Observation";
const sourceUrl = (x) => x?.url || x?.source_url;
const dated = (d) => (d ? dateLabel(d) : "Date unavailable");
function Source({ url, children = "View source" }) {
  return /^https?:\/\//i.test(url || "") ? (
    <a className="mk-source" href={url} target="_blank" rel="noreferrer">
      {children}
      <Mark name="external" size={12} />
    </a>
  ) : null;
}
function NoData({ children }) {
  return <p className="mk-empty">{children}</p>;
}
function Card({ title, children, id, action, extra = "" }) {
  return (
    <section id={id} className={"mk-panel " + extra}>
      <header className="mk-panel-head">
        <h2>{title}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}
function Tabs({ tabs, value, change }) {
  return (
    <div className="mk-tabs" aria-label="Sections">
      {tabs.map((t) => (
        <button key={t} aria-pressed={t === value} onClick={() => change(t)}>
          {t}
        </button>
      ))}
    </div>
  );
}
function Table({ headers, rows }) {
  return (
    <div className="mk-data-table">
      <table>
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((v, j) => (
                <td key={j}>{v}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function CTA({ item, create, busy }) {
  return (
    <button
      disabled={busy}
      className="mk-evidence-btn"
      onClick={() => create(item)}
    >
      <Mark name="studio" size={14} />
      {busy ? "Opening Studio…" : "Create content from this"}
      <Mark name="arrow" size={13} />
    </button>
  );
}
function Quote({ row }) {
  return (
    <blockquote className="mk-quote">
      <p>“{row.quote || row.body}”</p>
      <footer>
        {[
          label(row.source),
          row.date ? dateLabel(row.date) : null,
          row.rating != null ? number(row.rating, 1) + " ★" : null,
        ]
          .filter(Boolean)
          .join(" · ")}{" "}
        <Source url={sourceUrl(row)} />
      </footer>
    </blockquote>
  );
}
function Why({ item }) {
  const docs = array(
    item.evidence ||
      item.evidence_quotes ||
      item.review_evidence ||
      item.evidence_examples,
  );
  const urls = array(
    item.evidence_urls || item.source_urls || item.evidence_sources,
  );
  const method =
    item.threshold ||
    item.trigger_threshold ||
    item.method ||
    item.launch_basis;
  const numeric = Object.entries(item.metric_values || {})
    .filter(([, v]) => typeof v === "number")
    .slice(0, 5);
  return method ||
    docs.length ||
    urls.length ||
    numeric.length ||
    item.n != null ? (
    <details className="mk-why">
      <summary>Why?</summary>
      {method && (
        <p>
          {typeof method === "string"
            ? label(method)
            : Object.values(method)
                .filter((v) => typeof v === "string")
                .join(" · ")}
        </p>
      )}
      {item.n != null && <p>{number(item.n)} observations</p>}
      {numeric.length > 0 && (
        <div className="mk-fact-list">
          {numeric.map(([k, v]) => (
            <span key={k}>
              {label(k)} <b>{number(v, 2)}</b>
            </span>
          ))}
        </div>
      )}
      {docs
        .slice(0, 3)
        .map((d, i) =>
          d?.quote ? (
            <Quote row={d} key={i} />
          ) : (
            <Source key={i} url={typeof d === "string" ? d : sourceUrl(d)} />
          ),
        )}
      {urls.slice(0, 3).map((u, i) => (
        <Source key={i} url={typeof u === "string" ? u : sourceUrl(u)}>
          Source {i + 1}
        </Source>
      ))}
    </details>
  ) : null;
}
function Evidence({ item, kind, create, busy }) {
  return (
    <article id={item.id} className="mk-evidence">
      <div className="mk-evidence-type">
        <i />
        {label(kind)}
      </div>
      <h3>{titleOf(item)}</h3>
      <Why item={item} />
      <CTA item={item} create={create} busy={busy} />
    </article>
  );
}
function EvidenceList({ items = [], kind, create, busy, empty }) {
  if (!items.length)
    return (
      <NoData>{empty || "No qualifying observations for this date."}</NoData>
    );
  return (
    <div className="mk-evidence-grid">
      {items.map((item, i) => (
        <Evidence
          key={item.id || i}
          item={item}
          kind={kind || item.type || item.quadrant}
          create={create}
          busy={busy}
        />
      ))}
    </div>
  );
}
function ProductImage({ src, alt }) {
  const [failed, setFailed] = useState(false);
  return src && !failed ? (
    <img
      loading="lazy"
      src={src + (src.includes("?") ? "&" : "?") + "width=540"}
      alt={alt}
      onError={() => setFailed(true)}
    />
  ) : (
    <span className="mk-product-placeholder">
      <Mark name="products" size={34} />
    </span>
  );
}
export function Products({ data, navigate, query = "" }) {
  const [text, setText] = useState(query),
    [limit, setLimit] = useState(16);
  useEffect(() => {
    setText(query);
    setLimit(16);
  }, [query, data]);
  const all = data.products || [],
    visible = all.filter((p) =>
      (p.title + " " + p.handle + " " + (p.hero_ingredient || ""))
        .toLowerCase()
        .includes(text.toLowerCase()),
    );
  return (
    <div className="mk-detail-view">
      <div className="mk-list-head">
        <div>
          <span className="mk-overline">DOT &amp; KEY CATALOG</span>
          <h2>{number(visible.length)} products</h2>
        </div>
        <label className="mk-inline-search">
          <Mark name="search" size={16} />
          <input
            type="search"
            aria-label="Filter products"
            placeholder="Filter products…"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setLimit(16);
            }}
          />
        </label>
      </div>
      {visible.length ? (
        <div className="mk-products-grid">
          {visible.slice(0, limit).map((p) => (
            <button
              key={p.handle}
              className="mk-product"
              onClick={() => navigate("products", { product: p.handle })}
            >
              <div className="mk-product-img">
                <ProductImage src={p.image} alt="" />
              </div>
              <div className="mk-product-text">
                <small>{p.hero_ingredient || p.category}</small>
                <h3>{p.title}</h3>
                <div>
                  <b>{price(p.price)}</b>
                  {p.mrp > p.price && <del>{price(p.mrp)}</del>}
                  <Mark name="right" size={16} />
                </div>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <NoData>No products match this search.</NoData>
      )}
      {visible.length > limit && (
        <button className="mk-button" onClick={() => setLimit((x) => x + 16)}>
          Show more products
        </button>
      )}
    </div>
  );
}
export function ProductDetail({ data, navigate, create, busy }) {
  const [tab, setTab] = useState("Listings"),
    [limit, setLimit] = useState(12),
    p = data.product || {},
    snaps = data.snapshots || [],
    reviews = data.reviews || [],
    listings = data.listings || [];
  return (
    <div className="mk-detail-view">
      <button className="mk-text-btn" onClick={() => navigate("products")}>
        <Mark name="back" size={15} /> Back to products
      </button>
      <div className="mk-product-hero">
        <div className="mk-product-img">
          <ProductImage src={p.image || p.images?.[0]} alt={p.title} />
        </div>
        <div>
          <span className="mk-overline">{label(p.category)}</span>
          <h2>{p.title}</h2>
          <div className="mk-price">
            {price(p.price)} {p.mrp > p.price && <del>{price(p.mrp)}</del>}
          </div>
          <p>
            {[p.hero_ingredient, p.size, p.spf ? "SPF " + p.spf : null]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <Source url={p.url}>Official product page</Source>
          <button
            disabled={busy}
            className="mk-button mk-dark"
            onClick={() => create({ handle: p.handle })}
          >
            <Mark name="studio" />
            Open in Studio
          </button>
        </div>
      </div>
      <Tabs
        tabs={["Listings", "Price history", "Reviews"]}
        value={tab}
        change={setTab}
      />
      {tab === "Listings" && (
        <Card title="Marketplace listings">
          {listings.length ? (
            <Table
              headers={["Marketplace", "Listing", "Price", "Rating", "Reviews"]}
              rows={listings.map((l) => [
                label(l.market),
                <Source url={l.url}>{l.title || "View listing"}</Source>,
                price(l.price),
                number(l.rating, 1),
                number(l.review_count),
              ])}
            />
          ) : (
            <NoData>No marketplace listings on this date.</NoData>
          )}
        </Card>
      )}
      {tab === "Price history" && (
        <Card title="Observed prices">
          {snaps.length ? (
            <Table
              headers={["Observed on", "Marketplace", "Price", "MRP", "Rating"]}
              rows={snaps.map((s) => [
                dated(s.captured_at),
                label(s.market),
                price(s.price),
                price(s.mrp),
                number(s.rating, 1),
              ])}
            />
          ) : (
            <NoData>No dated price observations.</NoData>
          )}
        </Card>
      )}
      {tab === "Reviews" && (
        <Card title={number(reviews.length) + " sampled reviews"}>
          {reviews.length ? (
            reviews.slice(0, limit).map((r, i) => <Quote key={i} row={r} />)
          ) : (
            <NoData>No sampled reviews for this product.</NoData>
          )}
          {reviews.length > limit && (
            <button
              className="mk-button"
              onClick={() => setLimit((x) => x + 16)}
            >
              Show more reviews
            </button>
          )}
        </Card>
      )}
    </div>
  );
}
function Radar({ own = {}, peer = {}, brand }) {
  const keys = Object.keys(own)
    .filter((k) => own[k] != null && peer[k] != null)
    .slice(0, 6);
  if (keys.length < 3)
    return (
      <NoData>
        Shared aspect scores are available for fewer than three aspects.
      </NoData>
    );
  const cx = 166,
    cy = 108,
    r = 74;
  const xy = (i, scale) => [
    cx + Math.cos((i * 2 * Math.PI) / keys.length - Math.PI / 2) * r * scale,
    cy + Math.sin((i * 2 * Math.PI) / keys.length - Math.PI / 2) * r * scale,
  ];
  const points = (data, scale) =>
    keys
      .map((k, i) =>
        xy(i, data ? Math.min(1, Math.max(0, (data[k] + 1) / 2)) : scale).join(
          ",",
        ),
      )
      .join(" ");
  return (
    <>
      <svg viewBox="0 0 332 220" className="mk-radar" role="img">
        <title>Net sentiment for shared review aspects</title>
        <desc>
          Each spoke represents one aspect. The centre represents minus one, and
          the outer edge plus one.
        </desc>
        {[0.25, 0.5, 0.75, 1].map((n) => (
          <polygon
            key={n}
            points={points(null, n)}
            fill="none"
            stroke="#dbded8"
          />
        ))}
        {keys.map((k, i) => (
          <line
            key={k}
            x1={cx}
            y1={cy}
            x2={xy(i, 1)[0]}
            y2={xy(i, 1)[1]}
            stroke="#dcdfd8"
          />
        ))}
        <polygon
          points={points(own)}
          fill="#82b51c33"
          stroke="#779c31"
          strokeWidth="2"
        />
        <polygon
          points={points(peer)}
          fill="#22bce033"
          stroke="#169ebc"
          strokeWidth="2"
        />
        {keys.map((k, i) => {
          const [x, y] = xy(i, 1.15);
          return (
            <text
              key={k}
              x={x}
              y={y}
              textAnchor={x < cx - 6 ? "end" : x > cx + 6 ? "start" : "middle"}
            >
              {label(k)}
            </text>
          );
        })}
      </svg>
      <div className="mk-radar-key">
        <i />
        Dot &amp; Key <i />
        {brand}
      </div>
      <Facts
        caption="Net sentiment per aspect"
        rows={keys.map((k) => [
          label(k),
          number(own[k], 2),
          number(peer[k], 2),
        ])}
      />
    </>
  );
}
export function Competitors({
  data,
  category,
  asOf,
  create,
  busy,
  card,
  version,
  retry,
}) {
  const [selected, setSelected] = useState(0),
    rows = data.competitors || [],
    peer = rows[selected] || rows[0] || {};
  const launches = useMarketData(
      withQuery("/api/launches", { category, as_of: asOf }),
      null,
      version,
    ),
    signals = (data.brand_signals || []).filter(
      (s) => s.source === "crustdata_company",
    );
  useEffect(() => {
    const index = rows.findIndex((r) => r.id === card);
    if (index >= 0) setSelected(index);
  }, [card, rows]);
  return (
    <div className="mk-detail-view">
      <div className="mk-duo">
        <Card title="Top competitors">
          <div className="mk-ranked">
            {rows.map((r, i) => (
              <button
                id={r.id}
                key={r.product_ref}
                className={i === selected ? "selected" : ""}
                onClick={() => setSelected(i)}
              >
                <b>{String(r.rank).padStart(2, "0")}</b>
                <span>
                  <strong>{r.brand}</strong>
                  <small>{r.title}</small>
                </span>
                <span className="mk-rank-price">
                  {price(r.price)}
                  <small>{number(r.rating, 1)} ★</small>
                </span>
                <Mark name="right" size={15} />
              </button>
            ))}
            {!rows.length && (
              <NoData>No competitors ranked on this date.</NoData>
            )}
          </div>
        </Card>
        <Card title="Aspect comparison">
          <p className="mk-caption">
            Dot &amp; Key and {peer.brand || "a ranked competitor"}
          </p>
          <Radar
            own={data.own_aspects}
            peer={peer.aspects}
            brand={peer.brand}
          />
          {peer.id && (
            <>
              <Source url={peer.url}>Marketplace listing</Source>
              <CTA item={peer} busy={busy} create={create} />
            </>
          )}
        </Card>
      </div>
      <Card title="Competitor launches" id="launches">
        {launches.error ? (
          <Status error={launches.error} retry={retry} />
        ) : !launches.data ? (
          <p aria-busy="true">Loading launches…</p>
        ) : launches.data.launches?.length ? (
          <div className="mk-feed">
            {launches.data.launches.map((r, i) => (
              <article key={r.id || i} id={r.id}>
                <time>{dated(r.date || r.first_seen)}</time>
                <div>
                  <small>{r.brand}</small>
                  <h3>{r.title}</h3>
                  <Source url={r.url} />
                  <Why item={r} />
                </div>
                <CTA item={r} busy={busy} create={create} />
              </article>
            ))}
          </div>
        ) : (
          <NoData>No launch candidates in this period.</NoData>
        )}
      </Card>
      <Card title="Brand momentum">
        {signals.length ? (
          <Table
            headers={[
              "Brand",
              "Company scope",
              "Followers",
              "Quarterly growth",
              "Source",
            ]}
            rows={signals.map((s) => [
              s.brand,
              label(s.entity_scope),
              number(s.followers?.count),
              s.followers?.qoq_percent == null
                ? "—"
                : number(s.followers.qoq_percent, 1) + "%",
              label(s.source),
            ])}
          />
        ) : (
          <NoData>No Crustdata company signals for this cohort.</NoData>
        )}
      </Card>
    </div>
  );
}
export function Customers({ data, create, busy }) {
  const own = data.metrics?.brands?.["Dot & Key"] || {},
    aspects = Object.entries(own.aspects || {})
      .filter(([, v]) => v.mentions)
      .sort((a, b) => b[1].mentions - a[1].mentions);
  return (
    <div className="mk-detail-view">
      <Card
        title="Customer sentiment"
        action={
          <span className="mk-tag lime">
            {number(own.review_count)} sampled reviews
          </span>
        }
      >
        <div className="mk-aspects">
          {aspects.map(([k, v]) => {
            const id = "aspect:" + k;
            return (
              <article id={id} key={k}>
                <div>
                  <h3>{label(k)}</h3>
                  <span>{number(v.mentions)} mentions</span>
                </div>
                <div
                  className="mk-sentiment-track"
                  aria-label={
                    number(v.pos) + " positive, " + number(v.neg) + " negative"
                  }
                >
                  <i style={{ flex: v.pos, background: "#91b644" }} />
                  <i
                    style={{ flex: v.mixed + v.neutral, background: "#caccc7" }}
                  />
                  <i style={{ flex: v.neg, background: "#ee97af" }} />
                </div>
                <p>
                  {v.nss == null
                    ? "Insufficient directional evidence"
                    : "Net sentiment " + number(v.nss, 2)}{" "}
                  · Complaint lift {number(v.complaint_lift, 1)}×
                </p>
                <Why item={v} />
                <CTA
                  item={{ id, title: label(k) }}
                  busy={busy}
                  create={create}
                />
              </article>
            );
          })}
        </div>
        {!aspects.length && (
          <NoData>No aspect mentions for this sample.</NoData>
        )}
        <div className="mk-sentiment-key">
          Positive <i /> Mixed or neutral <i /> Negative
        </div>
      </Card>
      <Card title="Customer requests">
        <EvidenceList
          items={data.gaps?.unmet_needs}
          kind="Unmet need"
          create={create}
          busy={busy}
          empty="No repeated customer request met the evidence threshold."
        />
      </Card>
      <Card title="In customers’ words">
        {array(own.evidence).length ? (
          own.evidence.slice(0, 8).map((r, i) => <Quote key={i} row={r} />)
        ) : (
          <NoData>No attributable quotes for this category.</NoData>
        )}
      </Card>
    </div>
  );
}
export function Strategy({ data, create, busy, card }) {
  const [tab, setTab] = useState("SWOT");
  const swot = Object.entries(data.swot || {}),
    gaps = data.gaps || {},
    trends = data.trends || {},
    f = data.forecast || {},
    recs = array(data.recommendations);
  const gapItems = [
    ...array(gaps.whitespace),
    ...array(gaps.category_pain),
    ...array(gaps.unmet_needs),
  ];
  const terms = array(trends.terms),
    rising = new Set(array(trends.trending).map((t) => t.id));
  useEffect(() => {
    if (card === "forecast") setTab("Forecast");
    else if (gapItems.some((i) => i.id === card)) setTab("Gaps");
    else if (terms.some((i) => i.id === card)) setTab("Trends");
    else if (recs.some((i) => i.id === card)) setTab("Recommendations");
    else if (card) setTab("SWOT");
  }, [card, data]);
  return (
    <div className="mk-detail-view">
      <Tabs
        tabs={["SWOT", "Gaps", "Trends", "Forecast", "Recommendations"]}
        value={tab}
        change={setTab}
      />
      {tab === "SWOT" &&
        swot.map(([k, items], i) => (
          <Card
            key={k}
            id={i === 0 ? "swot" : undefined}
            title={
              {
                strength: "Strengths",
                weakness: "Weaknesses",
                opportunity: "Opportunities",
                threat: "Threats",
              }[k] || label(k)
            }
          >
            <EvidenceList items={items} kind={k} create={create} busy={busy} />
          </Card>
        ))}
      {tab === "Gaps" && (
        <Card title="Market gaps">
          <EvidenceList
            items={gapItems}
            kind="Market gap"
            create={create}
            busy={busy}
          />
        </Card>
      )}
      {tab === "Trends" && (
        <Card title="Trend signals">
          {!rising.size && (
            <p className="mk-caption">
              No term meets the cross-source threshold for a rising trend.
            </p>
          )}
          <EvidenceList
            items={terms.map((t) => ({
              ...t,
              title: label(t.term),
              type: rising.has(t.id) ? "Rising trend" : "Tracked term",
            }))}
            create={create}
            busy={busy}
          />
        </Card>
      )}
      {tab === "Forecast" && (
        <Card id="forecast" title="Demand forecast">
          <div className="mk-metric">{percent(f.forecast_growth, true)}</div>
          <p className="mk-caption">
            {label(f.status)} · {f.source}
          </p>
          <StepChart series={f.series} projection={f.projection} />
          <Why item={f} />
          <CTA
            item={{ id: "forecast", title: "Demand forecast" }}
            busy={busy}
            create={create}
          />
        </Card>
      )}
      {tab === "Recommendations" && (
        <Card title="Go-to-market recommendations">
          <EvidenceList items={recs} create={create} busy={busy} />
        </Card>
      )}
    </div>
  );
}
