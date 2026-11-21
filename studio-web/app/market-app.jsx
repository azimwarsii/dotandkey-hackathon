"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  Mark,
  Sheet,
  Status,
  VIEWS,
  CATEGORIES,
  withQuery,
  useMarketData,
  invalidate,
  onlineForAction,
  loadJSON,
  label,
  dateLabel,
} from "./market-shared";
import { Overview } from "./market-charts";
import { TourCoach } from "./guided-tour";
import ProductPicker from "./product-picker";
import AppExperience from "./experience";
import "./market.css";

const Studio = dynamic(() => import("./studio"), { loading: () => <Status /> });
const MarketCommand = dynamic(() => import("./market-command"));
const Competitors = dynamic(
  () => import("./market-details").then((m) => m.Competitors),
  { loading: Status },
);
const Products = dynamic(
  () => import("./market-details").then((m) => m.Products),
  { loading: Status },
);
const ProductDetail = dynamic(
  () => import("./market-details").then((m) => m.ProductDetail),
  { loading: Status },
);
const Strategy = dynamic(
  () => import("./market-details").then((m) => m.Strategy),
  { loading: Status },
);
const Customers = dynamic(
  () => import("./market-details").then((m) => m.Customers),
  { loading: Status },
);
const headings = {
  overview: "Market overview",
  products: "Products",
  competitors: "Competitors",
  customers: "Customers",
  strategy: "Strategy",
  studio: "Content Studio",
};
const subtitles = {
  overview: "Category performance across the skincare market.",
  products: "Explore the Dot & Key catalog and marketplace listings.",
  competitors: "Compare ranked products and track new launches.",
  customers: "Explore sentiment, complaints and requests in customer reviews.",
  strategy: "Turn category evidence into a go-to-market decision.",
};
function normalRoute(input) {
  const route = { ...input };
  if (route.run && (!VIEWS.includes(route.view) || route.view === "overview")) {
    route.studioStep = route.studioStep || route.view;
    route.view = "studio";
  }
  if (!VIEWS.includes(route.view)) route.view = "overview";
  if (!route.category) route.category = "Sunscreen";
  return route;
}
function routeFromLocation() {
  return normalRoute({
    ...Object.fromEntries(new URLSearchParams(location.search)),
    ...(location.hash
      ? { card: decodeURIComponent(location.hash.slice(1)) }
      : {}),
  });
}
function pathFor(r) {
  if (r.view === "studio") return null;
  if (r.view === "products")
    return withQuery(
      r.product
        ? "/api/products/" + encodeURIComponent(r.product)
        : "/api/products",
      r.product ? { as_of: r.as_of } : { category: r.category, as_of: r.as_of },
    );
  if (r.view === "customers" || r.view === "strategy")
    return withQuery(
      "/api/category/" + encodeURIComponent(r.category) + "/insights",
      { as_of: r.as_of },
    );
  return withQuery("/api/" + r.view, {
    category: r.category,
    as_of: r.as_of,
    compare: r.view === "overview" ? r.compare : null,
  });
}
const dayOffset = (s, n) => {
  const d = new Date(s + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
function Dates({ asOf, compare, close, change }) {
  const [a, setA] = useState(asOf),
    [b, setB] = useState(compare);
  return (
    <Sheet title="Reporting dates" close={close}>
      <form
        className="mk-date-form"
        onSubmit={(e) => {
          e.preventDefault();
          change(a, b);
          close();
        }}
      >
        <label>
          As of
          <input
            type="date"
            required
            value={a}
            onChange={(e) => setA(e.target.value)}
          />
        </label>
        <label>
          Compared to
          <input
            type="date"
            required
            max={a}
            value={b}
            onChange={(e) => setB(e.target.value)}
          />
        </label>
        <div className="mk-shortcuts">
          {[7, 30, 90].map((n) => (
            <button
              type="button"
              disabled={!a}
              key={n}
              onClick={() => setB(dayOffset(a, -n))}
            >
              Last {n} days
            </button>
          ))}
        </div>
        <button className="mk-button mk-dark">
          Apply dates <Mark name="arrow" size={15} />
        </button>
      </form>
    </Sheet>
  );
}
export default function MarketApp({
  initialRoute = {},
  initialData = null,
  initialRun = null,
  initialDate,
  initialWelcome,
}) {
  const [route, setRoute] = useState(() => normalRoute(initialRoute)),
    [sheet, setSheet] = useState(null),
    [tourStep, setTourStep] = useState(null),
    [version, setVersion] = useState(0),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [source, setSource] = useState(null),
    [refreshing, setRefreshing] = useState(""),
    job = useRef(null);
  const { view, category, product, card } = route,
    initialPath = pathFor(normalRoute(initialRoute)),
    path = pathFor(route),
    state = useMarketData(
      path,
      path && path === initialPath ? initialData : null,
      version,
    );
  const summaryURL = withQuery("/api/overview", {
    category,
    as_of: route.as_of,
    compare: route.compare,
  });
  const otherSummary = useMarketData(
    path === summaryURL ? null : summaryURL,
    path !== summaryURL && initialPath === summaryURL ? initialData : null,
    version,
  ).data;
  const summary = path === summaryURL ? state.data : otherSummary;
  const categories = summary?.categories?.map((c) => c.category) || CATEGORIES,
    asOf = route.as_of || summary?.as_of || initialDate,
    compare = route.compare || summary?.compare || dayOffset(asOf, -30);
  const picker = useMarketData(
    sheet === "pick-product"
      ? withQuery("/api/products", { category, as_of: asOf })
      : null,
    null,
    version,
  );
  const navigate = useCallback((v, args = {}) => {
    const prev = routeFromLocation(),
      next = normalRoute({
        view: v,
        category: prev.category,
        as_of: prev.as_of,
        compare: prev.compare,
        ...args,
      });
    const params = { ...next };
    delete params.card;
    const url =
      withQuery("/", params) +
      (next.card ? "#" + encodeURIComponent(next.card) : "");
    history.pushState(null, "", url);
    setTourStep((current) => {
      if (!current) return null;
      if (next.view === "products" && next.product)
        return next.tab === "reviews" ? "evidence" : "product";
      if (next.view === "studio" && next.run === "watermelon-demo")
        return (
          {
            overview: "brief",
            swipe: "references",
            inspect: "breakdown",
            video: "video",
          }[next.studioStep] || null
        );
      return null;
    });
    setRoute(next);
    setSheet(null);
    if (!next.card) window.scrollTo({ top: 0, behavior: "instant" });
  }, []);
  useEffect(() => {
    const back = () => {
      setTourStep(null);
      const next = routeFromLocation();
      setRoute((prev) =>
        JSON.stringify(prev) === JSON.stringify(next) ? prev : next,
      );
      setSheet(null);
    };
    back();
    window.addEventListener("popstate", back);
    const key = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSheet((s) => (s === "search" ? null : "search"));
      }
    };
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("popstate", back);
      window.removeEventListener("keydown", key);
      job.current?.close();
    };
  }, []);
  useEffect(() => {
    if (!path || initialPath !== path || !initialData) return;
    // The browser fetch also makes server-rendered dashboards available offline.
    loadJSON(path, true).catch(() => {});
  }, [path, initialPath, initialData]);
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(""), 5500);
    return () => clearTimeout(t);
  }, [notice]);
  useEffect(() => {
    if (!card || !state.data) return;
    let timer, obs;
    const reveal = () => {
      const el = document.getElementById(card);
      if (!el) return false;
      el.scrollIntoView({ block: "center", behavior: "instant" });
      el.classList.add("mk-highlight");
      timer = setTimeout(() => el.classList.remove("mk-highlight"), 1800);
      return true;
    };
    const frame = requestAnimationFrame(() => {
      if (!reveal()) {
        obs = new MutationObserver(() => {
          if (reveal()) obs.disconnect();
        });
        obs.observe(document.body, { childList: true, subtree: true });
      }
    });
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(timer);
      obs?.disconnect();
    };
  }, [card, state.data, view]);
  const retry = () => {
    invalidate();
    setVersion((n) => n + 1);
  };
  const exitTour = useCallback(() => setTourStep(null), []);
  function advanceTour() {
    if (tourStep === "product")
      return navigate("products", { product, category, tab: "reviews" });
    const step = {
      evidence: "overview",
      brief: "swipe",
      references: "inspect",
      breakdown: "video",
    }[tourStep];
    if (step)
      navigate("studio", {
        run: "watermelon-demo",
        category: "Sunscreen",
        studioStep: step,
      });
    else exitTour();
  }
  async function create(item) {
    if (busy || !onlineForAction()) return;
    if (item.id && !item.handle) {
      setSource(item);
      setSheet("pick-product");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        handle: item.handle,
        as_of: asOf,
        ...(item.id
          ? { evidence: { id: item.id, category, as_of: asOf } }
          : {}),
      };
      const res = await fetch("/studio-api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await res.json();
      if (!res.ok || !result.id)
        throw Error(
          typeof result.detail === "string"
            ? result.detail
            : "Unable to create a Studio brief.",
        );
      navigate("studio", { category, run: result.id, studioStep: "overview" });
    } catch (e) {
      setNotice(e.message || "Unable to open Studio.");
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    if (refreshing || !onlineForAction()) return;
    setRefreshing("Starting refresh");
    try {
      const res = await fetch(withQuery("/api/refresh", { category }), {
        method: "POST",
      });
      if (!res.ok) throw Error("Refresh could not start (" + res.status + ").");
      const result = await res.json();
      const events = new EventSource(
        "/api/jobs/" + encodeURIComponent(result.id) + "/events",
      );
      job.current = events;
      events.onmessage = (e) => {
        const data = JSON.parse(e.data);
        setRefreshing(label(data.stage || data.status));
        if (["complete", "failed", "interrupted"].includes(data.status)) {
          events.close();
          job.current = null;
          setRefreshing("");
          setNotice(
            data.status === "complete"
              ? "Market data refreshed."
              : String(data.error || "Refresh " + data.status),
          );
          if (data.status === "complete") retry();
        }
      };
      events.onerror = () => {
        if (events.readyState === EventSource.CLOSED) {
          setRefreshing("");
          setNotice(
            "Refresh progress disconnected. You can retry the refresh.",
          );
        }
      };
    } catch (e) {
      setRefreshing("");
      setNotice(e.message);
    }
  }
  function navItem(v, mobile = false) {
    const active =
      view === v || (mobile && view === "customers" && v === "strategy");
    return (
      <button
        key={v}
        className={
          "mk-nav-item" +
          (active ? " current" : "") +
          (v === "studio" ? " mk-studio-link" : "")
        }
        data-tour={["products", "strategy"].includes(v) ? v : undefined}
        data-tour-mobile={mobile ? v : undefined}
        aria-current={active ? "page" : undefined}
        onMouseEnter={() => {
          const p = pathFor({ ...route, view: v, product: null });
          if (p && v !== "customers" && v !== "strategy")
            loadJSON(p).catch(() => {});
        }}
        onClick={(event) => {
          const button = event.currentTarget,
            old = button.parentElement.querySelector(".current");
          const shift =
            old &&
            !window.matchMedia("(prefers-reduced-motion: reduce)").matches
              ? old.offsetLeft - button.offsetLeft
              : 0;
          navigate(v);
          if (shift)
            import("motion/mini")
              .then(({ animate }) => {
                const pill = button.querySelector(".mk-nav-highlight");
                if (pill)
                  animate(
                    pill,
                    {
                      transform: [
                        "translateX(" + shift + "px)",
                        "translateX(0px)",
                      ],
                    },
                    { duration: 0.2, ease: "easeOut" },
                  );
              })
              .catch(() => {});
        }}
      >
        {active && <span className="mk-nav-highlight" />}
        {(mobile || v === "studio") && (
          <Mark name={v} size={mobile ? 17 : 14} />
        )}
        <span>{label(v)}</span>
      </button>
    );
  }
  return (
    <>
      <div className="mk-canvas">
        <div className="mk-frame">
          <header className="mk-topbar">
            <button
              className="mk-brand"
              onClick={() => navigate("overview")}
              aria-label="Dot and Key, market overview"
            >
              <img
                src="/brand/logo.svg"
                width="278"
                height="65"
                alt="Dot & Key"
              />
              <span>
                Market
                <br />
                Studio
              </span>
            </button>
            <nav className="mk-nav" aria-label="Main navigation">
              {VIEWS.map((v) => navItem(v))}
            </nav>
            <div className="mk-tools">
              <button
                className="mk-icon mk-search-trigger"
                aria-label="Search workspace, Command K"
                onClick={() => setSheet("search")}
              >
                <Mark name="search" size={18} />
              </button>
              <button
                className="mk-icon"
                aria-label="Help and walkthrough"
                onClick={() => setSheet("help")}
              >
                <Mark name="help" size={18} />
              </button>
            </div>
          </header>
          <main className={"mk-main mk-view-" + view}>
            <div className="mk-crumb">
              <span className="mk-live-dot" />
              <span>Workspace</span>
              <Mark name="right" size={11} />
              <span>{label(view)}</span>
              {product && view === "products" && (
                <>
                  <Mark name="right" size={11} />
                  <span>Product detail</span>
                </>
              )}
            </div>
            <div className="mk-intro">
              <div>
                <h1>
                  {headings[view]}
                  <span className="mk-heading-dot">.</span>
                </h1>
                {subtitles[view] && <p>{subtitles[view]}</p>}
              </div>
              {view !== "studio" && (
                <div className="mk-controls">
                  <button
                    className="mk-control mk-category"
                    data-tour="category"
                    aria-label={"Change category, " + category}
                    onClick={() => setSheet("category")}
                  >
                    <Mark
                      name={category === "Sunscreen" ? "sun" : "stack"}
                      size={16}
                    />
                    {category}
                    <Mark name="chevron" size={14} />
                  </button>
                  <button
                    className="mk-control mk-date"
                    aria-label={
                      "Reporting dates, " + asOf + " compared to " + compare
                    }
                    onClick={() => setSheet("dates")}
                  >
                    <Mark name="date" size={16} />
                    <span>
                      {dateLabel(asOf)}
                      <small>vs {dateLabel(compare)}</small>
                    </span>
                    <Mark name="chevron" size={14} />
                  </button>
                  {view === "overview" && (
                    <button
                      className="mk-control mk-refresh"
                      onClick={refresh}
                      disabled={!!refreshing}
                      aria-label={refreshing || "Refresh data"}
                    >
                      <Mark name="refresh" size={16} />
                      <span>{refreshing || "Refresh data"}</span>
                    </button>
                  )}
                </div>
              )}
            </div>
            {["customers", "strategy"].includes(view) && (
              <div className="mk-mobile-research">
                <button
                  aria-pressed={view === "strategy"}
                  onClick={() => navigate("strategy")}
                >
                  Strategy
                </button>
                <button
                  aria-pressed={view === "customers"}
                  onClick={() => navigate("customers")}
                >
                  Customers
                </button>
              </div>
            )}
            <TourCoach step={tourStep} advance={advanceTour} exit={exitTour} />
            <div key={view} className="mk-view-body">
              {view === "studio" ? (
                <Studio
                  key={route.run || "watermelon-demo"}
                  embedded={true}
                  onRoute={(run, studioStep, cat, reference) =>
                    navigate("studio", {
                      run,
                      studioStep,
                      reference,
                      category: cat || category,
                    })
                  }
                  first={
                    initialRun && initialRoute.run === route.run
                      ? initialRun
                      : null
                  }
                  initialId={route.run || "watermelon-demo"}
                  initialView={route.studioStep}
                  initialReference={route.reference}
                  tourStep={tourStep}
                  product={product}
                />
              ) : state.error || !state.data ? (
                <Status error={state.error} retry={retry} />
              ) : view === "overview" ? (
                <Overview
                  data={state.data}
                  select={(c) => navigate("overview", { category: c })}
                  navigate={navigate}
                  create={create}
                  busy={busy}
                />
              ) : view === "products" ? (
                product ? (
                  <ProductDetail
                    data={state.data}
                    card={card}
                    startTab={route.tab}
                    onReviews={() => {
                      if (tourStep === "product") setTourStep("evidence");
                    }}
                    navigate={navigate}
                    create={create}
                    busy={busy}
                  />
                ) : (
                  <Products
                    data={state.data}
                    query={route.q}
                    navigate={navigate}
                  />
                )
              ) : view === "competitors" ? (
                <Competitors
                  data={state.data}
                  category={category}
                  asOf={route.as_of}
                  card={card}
                  version={version}
                  retry={retry}
                  create={create}
                  busy={busy}
                />
              ) : view === "customers" ? (
                <Customers data={state.data} create={create} busy={busy} />
              ) : (
                <Strategy
                  data={state.data}
                  card={card}
                  create={create}
                  busy={busy}
                />
              )}
            </div>
          </main>
          <div className="mk-dock-wrap">
            <button
              data-tour="ask"
              className="mk-dock"
              onClick={() => setSheet("ask")}
            >
              <span className="mk-dock-icon">
                <Mark name="studio" size={21} />
              </span>
              <strong>Search or ask</strong>
              <span className="mk-dock-question">
                Find a product, customer comment or campaign…
              </span>
              <kbd className="mk-slash">⌘ / Ctrl K</kbd>
              <span className="mk-dock-go">
                <Mark name="arrow" size={16} />
              </span>
            </button>
          </div>
          <nav className="mk-bottom-nav" aria-label="Mobile navigation">
            {VIEWS.filter((v) => v !== "customers").map((v) =>
              navItem(v, true),
            )}
          </nav>
        </div>
      </div>

      {sheet === "pick-product" && source && (
        <Sheet
          title="Choose the product for this campaign"
          close={() => setSheet(null)}
        >
          {notice && <p role="alert">{notice}</p>}
          <p className="picker-source">{source.title}</p>
          <p className="mk-search-context">
            {category} · {dateLabel(asOf)}
          </p>
          {picker.data ? (
            <ProductPicker
              products={picker.data.products}
              busy={busy}
              choose={(handle) => create({ ...source, handle })}
            />
          ) : (
            <Status error={picker.error} retry={retry} />
          )}
        </Sheet>
      )}
      {sheet === "category" && (
        <Sheet title="Choose category" close={() => setSheet(null)}>
          <div className="mk-categories">
            {categories.map((c) => (
              <button
                key={c}
                aria-pressed={c === category}
                onClick={() => navigate(view, { category: c })}
              >
                <Mark name={c === "Sunscreen" ? "sun" : "stack"} size={16} />
                {c}
                {c === category && <Mark name="check" size={16} />}
              </button>
            ))}
          </div>
        </Sheet>
      )}
      {sheet === "dates" && (
        <Dates
          asOf={asOf}
          compare={compare}
          close={() => setSheet(null)}
          change={(a, b) =>
            navigate(view, {
              as_of: a,
              compare: b,
              product,
              run: route.run,
              studioStep: route.studioStep,
            })
          }
        />
      )}
      {sheet === "help" && (
        <Sheet title="Workspace help" close={() => setSheet(null)}>
          <div className="mk-help-items">
            <button
              className="mk-button"
              onClick={() => {
                setSheet(null);
                window.dispatchEvent(new Event("market:tour"));
              }}
            >
              <Mark name="help" />
              Replay the walkthrough
            </button>
            <button className="mk-button" onClick={() => setSheet("search")}>
              <Mark name="search" />
              Search the workspace <kbd>⌘ K</kbd>
            </button>
          </div>
        </Sheet>
      )}
      {["search", "ask"].includes(sheet) && (
        <MarketCommand
          category={category}
          categories={categories}
          run={route.run}
          asOf={asOf}
          navigate={navigate}
          tour={tourStep === "search"}
          exitTour={exitTour}
          demoBrief={() =>
            navigate("studio", {
              run: "watermelon-demo",
              category: "Sunscreen",
              studioStep: "overview",
            })
          }
          close={() => {
            setSheet(null);
            if (tourStep === "search") exitTour();
          }}
        />
      )}
      {notice && (
        <div role="status" className="mk-toast">
          {notice}
          <button
            aria-label="Dismiss notification"
            onClick={() => setNotice("")}
          >
            <Mark name="close" size={14} />
          </button>
        </div>
      )}
      <AppExperience
        welcomeInitially={initialWelcome}
        startTour={() => {
          setTourStep("search");
          setSheet("search");
        }}
        exitTour={exitTour}
        step={tourStep}
        view={view}
        asOf={summary?.as_of || state.data?.as_of || route.as_of}
      />
    </>
  );
}
