"use client";
import { useState, useEffect, useId, useSyncExternalStore } from "react";
import { useReducedMotion } from "motion/react";
import {
  Mark,
  Count,
  Facts,
  Sheet,
  label,
  number,
  percent,
  dateLabel,
} from "./market-shared";

const shortMonth = (m) =>
  m ? dateLabel(m.slice(0, 7) + "-01", { month: "short" }) : "";
const sum = (rows) => rows.reduce((v, r) => v + Number(r.total || 0), 0);
function Legend({ color, children }) {
  return (
    <span className="mk-legend">
      <i style={{ background: color }} />
      {children}
    </span>
  );
}
function Widget({
  id,
  title,
  icon,
  tone,
  children,
  method,
  rows,
  tour,
  extra = "",
}) {
  const [open, setOpen] = useState(false);
  return (
    <section id={id} className={"mk-widget " + extra} data-tour={tour}>
      <header className="mk-widget-head">
        <span className={"mk-symbol " + tone}>
          <Mark name={icon} size={17} />
        </span>
        <h2>{title}</h2>
        <button
          className="mk-menu"
          aria-label={title + " details"}
          onClick={() => setOpen(true)}
        >
          <Mark name="menu" />
        </button>
      </header>
      {children}
      {open && (
        <Sheet title={title} close={() => setOpen(false)}>
          <p>{method}</p>
          {rows?.length > 0 && (
            <div className="mk-data-table">
              <table>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i}>
                      {r.map((v, j) => (
                        <td key={j}>{v}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Sheet>
      )}
    </section>
  );
}
const abbrev = {
  "Lip Balm": "Lip balm",
  Moisturiser: "Moist.",
  "Face Wash": "Wash",
  Sunscreen: "Sun",
};
const mobileQuery = "(max-width: 767px)";
const subscribeMobile = (callback) => {
  const media = window.matchMedia(mobileQuery);
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
};
export function Opportunity({ rows = [], category, onSelect }) {
  const id = useId().replaceAll(":", ""),
    [point, setPoint] = useState(null);
  const ranked = [...rows].sort(
    (a, b) =>
      (b.opportunity_score ?? -Infinity) - (a.opportunity_score ?? -Infinity),
  );
  const chosen = ranked.find((x) => x.category === category);
  const hovered = ranked.find((x) => x.category === point);
  const listing = ranked.map((d) => [
    d.category,
    number(d.opportunity_score, 3),
    percent(d.forecast_growth, true),
    percent(d.dk_share),
  ]);
  const mobile = useSyncExternalStore(
    subscribeMobile,
    () => window.matchMedia(mobileQuery).matches,
    () => false,
  );
  const displayed = mobile ? ranked.slice(0, 5) : ranked;
  if (mobile && chosen && !displayed.includes(chosen))
    displayed[displayed.length - 1] = chosen;
  const w = mobile ? 320 : 490,
    h = 133,
    base = 108,
    space = 8,
    bar = (w - (displayed.length - 1) * space) / Math.max(1, displayed.length);
  const maximum = Math.max(
    ...ranked.map((r) => Math.max(0, r.opportunity_score ?? 0)),
    0.01,
  );
  const height = (d) =>
    d.opportunity_score == null
      ? 2
      : Math.max(4, (Math.max(0, d.opportunity_score) / maximum) * 83);
  return (
    <Widget
      id="opportunity"
      title="Category opportunity"
      icon="opportunity"
      tone="lime"
      tour="opportunity"
      extra="mk-opportunity"
      rows={listing}
      method="The score combines forecast growth, Dot & Key’s share of observed reviews and the number of distinct gaps. A dash indicates insufficient evidence."
    >
      <div className="mk-metric">
        <Count value={chosen?.opportunity_score} digits={3} />
        {chosen?.opportunity_score != null && (
          <span className="mk-tag lime">Rank {ranked.indexOf(chosen) + 1}</span>
        )}
      </div>
      <p className="mk-caption">
        Opportunity score <span>·</span> {category}
      </p>
      <div className="mk-bars-wrap">
        <svg
          viewBox={"-2 0 " + (w + 4) + " " + h}
          role="group"
          aria-label="Opportunity scores by category"
        >
          <title>Category opportunity scores</title>
          <desc>
            Choose a category to update the dashboard. Scores are ordered from
            highest to lowest.
          </desc>
          <defs>
            <pattern
              id={id + "hatch"}
              width="5"
              height="5"
              patternUnits="userSpaceOnUse"
            >
              <rect width="5" height="5" fill="#edf0e6" />
              <path
                d="M-1 1l2-2M0 5l5-5M4 6l2-2"
                stroke="#929c84"
                strokeWidth="1"
              />
            </pattern>
            <linearGradient
              id={id + "green"}
              x1="0"
              x2=".25"
              y1="0"
              y2="1"
              gradientUnits="objectBoundingBox"
            >
              <stop stopColor="#c2eb67" />
              <stop offset="1" stopColor="#8cba35" />
            </linearGradient>
          </defs>
          {[30, 60, 90].map((y) => (
            <path
              key={y}
              d={"M0 " + y + "H" + w}
              stroke="#dadcd4"
              strokeDasharray="2 4"
            />
          ))}
          {displayed.map((d, i) => {
            const x = i * (bar + space),
              y = base - height(d),
              active = d.category === category;
            return (
              <g
                key={d.category}
                role="button"
                aria-label={
                  d.category + ", score " + number(d.opportunity_score, 3)
                }
                aria-pressed={active}
                tabIndex="0"
                onMouseEnter={() => setPoint(d.category)}
                onMouseLeave={() => setPoint(null)}
                onFocus={() => setPoint(d.category)}
                onBlur={() => setPoint(null)}
                onClick={() => onSelect(d.category)}
                onKeyDown={(e) => {
                  if (["Enter", " "].includes(e.key)) {
                    e.preventDefault();
                    onSelect(d.category);
                  }
                }}
              >
                <title>
                  {d.category +
                    " · Score " +
                    number(d.opportunity_score, 3) +
                    " · Forecast " +
                    percent(d.forecast_growth, true) +
                    " · D&K share " +
                    percent(d.dk_share)}
                </title>
                <rect
                  x={x}
                  y="6"
                  width={bar}
                  height={base + 20}
                  fill="transparent"
                />
                {i < displayed.length - 1 && (
                  <path
                    d={
                      "M" +
                      (x + bar - 2) +
                      " " +
                      y +
                      "l" +
                      (space + 4) +
                      " " +
                      (height(d) - height(displayed[i + 1]))
                    }
                    stroke="#a8b394"
                    strokeWidth="1.2"
                  />
                )}
                <rect
                  className="mk-grow-bar"
                  style={{ animationDelay: i * 40 + "ms" }}
                  x={x}
                  y={y}
                  width={bar}
                  height={height(d)}
                  rx="3"
                  fill={
                    d.opportunity_score == null
                      ? "#c9ccc6"
                      : "url(#" + id + (active ? "green" : "hatch") + ")"
                  }
                />
                <text
                  x={x + bar / 2}
                  y={base + 17}
                  textAnchor="middle"
                  className={active ? "active" : ""}
                >
                  {mobile ? d.category : abbrev[d.category] || d.category}
                </text>
                {active && (
                  <>
                    <rect
                      x={x + bar / 2 - 23}
                      y={y - 22}
                      width="46"
                      height="18"
                      rx="9"
                      fill="#23251e"
                    />
                    <text
                      x={x + bar / 2}
                      y={y - 10}
                      textAnchor="middle"
                      style={{ fill: "white", fontSize: 9 }}
                    >
                      {number(d.opportunity_score, 3)}
                    </text>
                  </>
                )}
              </g>
            );
          })}
        </svg>
        {hovered && (
          <div className="mk-chart-hint">
            {hovered.category} · Forecast{" "}
            {percent(hovered.forecast_growth, true)} · Share{" "}
            {percent(hovered.dk_share)}
          </div>
        )}
      </div>
      <div className="mk-card-foot">
        <Legend color="#9fc54e">Selected category</Legend>
        <span className="mk-hatch-key" />
        Other categories
      </div>
      <Facts
        rows={listing}
        caption="Category, opportunity score, forecast growth and review share"
      />
    </Widget>
  );
}
export function ReviewShare({ data = {} }) {
  const rows = data.markets || [],
    max = Math.max(1, ...rows.map((x) => x.review_volume || 0));
  return (
    <Widget
      id="review-share"
      title="D&K review share"
      icon="share"
      tone="lime"
      method="Dot & Key’s share of observed review volume across the six tracked brands. Marketplace rows show sampled review texts and the average star rating weighted by listing rating counts."
      rows={rows.map((r) => [
        label(r.market),
        number(r.review_volume),
        number(r.rating, 2) + " stars",
      ])}
    >
      <div className="mk-metric">
        <Count
          value={data.value == null ? null : data.value * 100}
          digits={1}
        />
        <em>%</em>
        {data.delta != null && (
          <span className="mk-tag lime">
            {data.delta >= 0 ? "+" : ""}
            {number(data.delta * 100, 1)} pp
          </span>
        )}
      </div>
      <p className="mk-caption">Across tracked marketplaces</p>
      <div className="mk-progress">
        {rows.map((row, i) => (
          <div className="mk-market-row" key={row.market}>
            <div>
              <span>{label(row.market)}</span>
              <b>{number(row.review_volume)}</b>
              <small>★ {number(row.rating, 1)}</small>
            </div>
            <div className="mk-track">
              <i
                className={i === 0 ? "solid" : ""}
                style={{ width: (100 * (row.review_volume || 0)) / max + "%" }}
              />
            </div>
          </div>
        ))}
      </div>
    </Widget>
  );
}
export function StepChart({ series = [], projection = [] }) {
  const id = useId().replaceAll(":", ""),
    plot = [...series, ...projection],
    width = 300,
    top = 11,
    bottom = 96;
  const max = Math.max(1, ...plot.map((r) => r.index ?? 0)),
    x = (i) => 5 + (i * (width - 10)) / Math.max(1, plot.length - 1),
    y = (v) => bottom - (v / max) * (bottom - top);
  const path = (rows, offset = 0) => {
    let d = "",
      previous = false;
    rows.forEach((r, i) => {
      if (r.index == null) {
        previous = false;
        return;
      }
      d +=
        (previous ? "H" + x(i + offset) + "V" : "M" + x(i + offset) + " ") +
        y(r.index);
      previous = true;
    });
    return d;
  };
  const line = path(series),
    last = series.findLastIndex((r) => r.index != null),
    forecast =
      last >= 0
        ? path(
            [
              series[last],
              ...Array(series.length - last - 1).fill({ index: null }),
              ...projection,
            ],
            last,
          )
        : path(projection, series.length);
  const nonNull = series.findIndex((r) => r.index != null);
  return (
    <div className="mk-line-wrap">
      <svg viewBox="0 0 300 116" role="img">
        <title>Demand index and forecast</title>
        <desc>
          Solid steps show observed review activity. Dashed steps show the
          projection.
        </desc>
        <defs>
          <linearGradient id={id + "fade"} x1="0" y1="0" x2="0" y2="1">
            <stop stopColor="#f866af" stopOpacity=".23" />
            <stop offset="1" stopColor="#ff81bf" stopOpacity=".01" />
          </linearGradient>
        </defs>
        {[20, 45, 70, 96].map((v) => (
          <path
            key={v}
            d={"M0 " + v + "H300"}
            stroke="#ddd9dc"
            strokeDasharray="2 4"
          />
        ))}
        {line && (
          <>
            <path
              d={line + "V" + bottom + "H" + x(nonNull) + "Z"}
              fill={"url(#" + id + "fade)"}
            />
            <path
              d={line}
              fill="none"
              stroke="#e6459a"
              strokeWidth="2.8"
              strokeLinejoin="round"
            />
          </>
        )}
        <path
          d={forecast}
          fill="none"
          stroke="#d65b9c"
          strokeWidth="2"
          strokeDasharray="4 3"
        />
        {last >= 0 && (
          <circle
            cx={x(last)}
            cy={y(series[last].index)}
            r="3.5"
            fill="#ef459e"
            stroke="white"
          />
        )}
        {[
          0,
          Math.floor(plot.length / 3),
          Math.floor((plot.length * 2) / 3),
          plot.length - 1,
        ]
          .filter((v, i, a) => v >= 0 && a.indexOf(v) === i)
          .map((v, i, a) => (
            <text
              key={v}
              y="113"
              x={x(v)}
              textAnchor={
                i === 0 ? "start" : i === a.length - 1 ? "end" : "middle"
              }
            >
              {shortMonth(plot[v]?.month)}
            </text>
          ))}
      </svg>
      <Facts
        rows={plot.map((r) => [r.month, number(r.index, 2)])}
        caption="Demand index by month"
      />
    </div>
  );
}
export function Demand({ data = {} }) {
  const observed = (data.series || []).filter((r) => r.index != null).at(-1);
  return (
    <Widget
      title="Demand index"
      icon="demand"
      tone="pink"
      rows={[...(data.series || []), ...(data.projection || [])].map((d) => [
        d.month,
        number(d.index, 2),
      ])}
      method="Monthly activity in dated marketplace reviews, indexed to the category baseline. Dashed steps show the forecast."
    >
      <div className="mk-metric">
        <Count value={observed?.index} digits={1} />
        {data.forecast_growth != null && (
          <span className="mk-tag pink">
            {percent(data.forecast_growth, true)}
          </span>
        )}
      </div>
      <p className="mk-caption">
        {observed
          ? shortMonth(observed.month) + " review activity"
          : "Monthly review activity"}
      </p>
      <StepChart {...data} />
      <div className="mk-card-foot">
        <Legend color="#ed549e">Observed</Legend>
        <span className="mk-dash-key" />
        Forecast
      </div>
    </Widget>
  );
}
export function DotChart({ rows = [], launch = false }) {
  const n = rows.length,
    max = Math.max(1, ...rows.map((r) => r.total || 0)),
    cols = 3,
    levels = 12,
    w = 360,
    h = 88;
  const positions = rows.flatMap((r, i) => {
    const lit = Math.max(
      r.total > 0 ? 1 : 0,
      Math.round(((r.total || 0) / max) * cols * levels),
    );
    return Array.from({ length: cols * levels }, (_, j) => {
      const isLit = j < lit,
        frac = (j + 0.5) / Math.max(lit, 1),
        color = launch
          ? "#26a9cf"
          : frac < r.positive / Math.max(1, r.total)
            ? "#83ac39"
            : frac < (r.positive + r.neutral) / Math.max(1, r.total)
              ? "#b2b7a6"
              : frac <
                  (r.positive + r.neutral + r.negative) / Math.max(1, r.total)
                ? "#ef98af"
                : "#939aa2";
      return (
        <circle
          key={i + "-" + j}
          cx={
            5 +
            ((i + ((j % cols) + 0.5) / (cols + 0.8)) * (w - 10)) /
              Math.max(1, n)
          }
          cy={h - 4 - (Math.floor(j / cols) * (h - 9)) / (levels - 1)}
          r={Math.min(2.65, ((w - 10) / Math.max(1, n) / cols) * 0.33)}
          fill={isLit ? color : "#e2e4de"}
        />
      );
    });
  });
  return (
    <div className="mk-dot-wrap">
      <svg viewBox={"0 0 " + w + " " + h} preserveAspectRatio="none" role="img">
        <title>
          {launch
            ? "Weekly competitor launches"
            : "Weekly review volume by sentiment"}
        </title>
        <desc>
          Each group of dots represents one week in the selected period.
        </desc>
        {positions}
      </svg>
      <div className="mk-dot-axis">
        {[0, Math.floor(n / 2), n - 1]
          .filter((v, i, a) => v >= 0 && a.indexOf(v) === i)
          .map((i) => (
            <span key={i}>
              {dateLabel(rows[i]?.week, { day: "numeric", month: "short" })}
            </span>
          ))}
      </div>
      <Facts
        rows={rows.map((r) => [r.week, number(r.total)])}
        caption="Weekly totals"
      />
    </div>
  );
}
export function Activity({ rows = [], launch = false }) {
  const peak = rows.reduce((p, r) => (r.total > (p?.total ?? 0) ? r : p), null),
    total = sum(rows);
  return (
    <Widget
      title={launch ? "Competitor launches" : "Review velocity"}
      icon={launch ? "launches" : "velocity"}
      tone={launch ? "cyan" : "lilac"}
      rows={rows.map((r) => [
        r.week,
        number(r.total),
        ...(launch
          ? []
          : [
              number(r.positive) + " positive",
              number(r.negative) + " negative",
              number(r.neutral) + " neutral",
              number(r.unrated) + " unrated",
            ]),
      ])}
      method={
        launch
          ? "Weekly counts of observed competitor launch candidates in the tracked catalogs."
          : "Sampled reviews grouped by week and sentiment for the current category."
      }
    >
      <div className="mk-metric mk-small-metric">
        <Count value={total} />
        <span className="mk-unit">{launch ? "launches" : "reviews"}</span>
      </div>
      <p className="mk-caption">
        {peak
          ? "Peak week of " +
            dateLabel(peak.week, { day: "numeric", month: "short" })
          : "Weekly observations"}
      </p>
      <DotChart rows={rows} launch={launch} />
      <div className="mk-card-foot">
        {launch ? (
          <Legend color="#26a9cf">Catalog launches</Legend>
        ) : (
          <>
            <Legend color="#83ac39">Positive</Legend>
            <Legend color="#b2b7a6">Neutral</Legend>
            <Legend color="#ef98af">Negative</Legend>
            {rows.some((r) => r.unrated > 0) && (
              <Legend color="#939aa2">Unrated</Legend>
            )}
          </>
        )}
      </div>
    </Widget>
  );
}
export function Insight({ items = [], create, busy }) {
  const [index, setIndex] = useState(0),
    [paused, setPaused] = useState(false),
    reduced = useReducedMotion();
  useEffect(() => {
    setIndex(0);
  }, [items]);
  useEffect(() => {
    if (paused || reduced || items.length < 2) return;
    const timer = setTimeout(
      () => setIndex((x) => (x + 1) % items.length),
      12000,
    );
    return () => clearTimeout(timer);
  }, [index, items, paused, reduced]);
  const item = items[index] || items[0];
  return (
    <section
      className="mk-widget mk-insight"
      data-tour="insight"
      aria-label="Top insights"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setPaused(false);
      }}
    >
      <div className="mk-insight-art" aria-hidden="true">
        <div />
      </div>
      <div className="mk-story-content">
        <header className="mk-widget-head">
          <span className="mk-symbol glass">
            <Mark name="studio" size={17} />
          </span>
          <h2>Top insights</h2>
          <span className="mk-story-n">
            {items.length ? String(index + 1).padStart(2, "0") : "00"} /{" "}
            {String(items.length).padStart(2, "0")}
          </span>
        </header>
        {item ? (
          <>
            <span className="mk-story-type">{label(item.type)}</span>
            <h3 key={item.id}>{item.title}</h3>
            <button
              disabled={busy}
              className="mk-create"
              onClick={() => create(item)}
            >
              {busy ? "Opening Studio…" : "Create content"}
              <Mark name="arrow" size={15} />
            </button>
          </>
        ) : (
          <p>No qualifying insight for this date.</p>
        )}
        <div className="mk-story-dots">
          {items.map((d, i) => (
            <button
              key={d.id}
              aria-label={"Show insight " + (i + 1)}
              aria-current={i === index ? "true" : undefined}
              onClick={() => setIndex(i)}
            >
              <i
                key={index}
                style={{ animationPlayState: paused ? "paused" : "running" }}
              />
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
export function Overview({ data, select, create, busy }) {
  return (
    <div className="mk-dashboard">
      <Opportunity
        rows={data.categories}
        category={data.category}
        onSelect={select}
      />
      <ReviewShare data={data.review_share} />
      <Demand data={data.demand} />
      <Activity rows={data.review_velocity} />
      <Activity rows={data.launch_velocity} launch />
      <Insight items={data.insights} create={create} busy={busy} />
    </div>
  );
}
