"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Badge,
  Card,
  Data,
  Empty,
  Icon,
  Inspector,
  Modal,
  Section,
  asList,
  nav,
  nice,
  textOf,
  urlFor,
} from "./ui";
import { Swipe, Inspect, Patterns } from "./research";
import { Concepts, Script, Video, Statics, Testing } from "./production";

const titles = {
  overview: "Campaign overview",
  swipe: "Swipe file",
  inspect: "Deconstruct",
  patterns: "Pattern board",
  concepts: "Concept slate",
  script: "Script & storyboard",
  video: "Video production",
  statics: "Ads & listings",
  testing: "Testing",
  lineage: "Lineage",
};
async function api(path, options) {
  const response = await fetch("/studio-api" + path, options);
  if (!response.ok) {
    let d;
    try {
      d = await response.json();
    } catch {}
    throw Error(
      typeof d?.detail === "string"
        ? d.detail
        : "Request failed (" + response.status + ")",
    );
  }
  return response.json();
}
const post = (path, body = {}) =>
  api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
function Overview({ s, asset, media, go, enter, inspect }) {
  const b = s.brief,
    p = b.product || {},
    photos = asList(p.local_images),
    cre = s.creative;
  const short =
    b.claim_sources?.find((f) => f.kind === "short_name")?.text ||
    p.title ||
    s.meta.handle;
  return (
    <>
      <article className="hero">
        <div className="hero-copy">
          <span className="eyebrow">
            <span className="live-dot" /> Current campaign
          </span>
          <h2>{short}</h2>
          <p>
            {[p.brand, p.category, p.spf && "SPF " + p.spf, p.size]
              .filter(Boolean)
              .join("  ·  ")}
          </p>
          <button
            className="primary"
            onClick={() =>
              inspect({
                title: "Product brief",
                inputs: { product: p.url, as_of: b.as_of },
                recipe: {
                  source: "Part 1 catalog and Part 2 findings",
                  scope: b.scope,
                },
                output: {
                  allowed_claims: b.allowed_claims,
                  audience: b.audience,
                  strengths: b.strengths,
                },
                checks: {
                  locked_claims: b.allowed_claims?.length,
                  source_links: asList(b.claim_sources).map((x) => ({
                    claim: x.text,
                    source: x.url,
                  })),
                },
              })
            }
          >
            Open product brief <Icon name="arrow" />
          </button>
        </div>
        <div className="hero-art">
          {photos.length > 0 && (
            <>
              <img className="hero-base" src={asset(photos[0])} alt="" />
              <img
                className={p.cutout ? "hero-pack" : "hero-product"}
                src={asset(p.cutout || photos[0])}
                alt={p.title}
              />
            </>
          )}
        </div>
      </article>
      <div className="stat-band">
        {[
          [s.posts.length, "Research posts", "swipe"],
          [s.patterns.length, "Patterns", "patterns"],
          [s.concepts.length, "Concepts", "concepts"],
          [asList(cre.variants).length, "Test variants", "testing"],
        ].map(([n, label, to]) => (
          <button key={label} onClick={() => go(to)}>
            <strong>{n}</strong>
            <span>{label}</span>
            <Icon name="northeast" size={14} />
          </button>
        ))}
      </div>
      <Section title="Campaign workspace">
        <div className="workspace-grid">
          {[
            [
              "swipe",
              "stack",
              "Research library",
              s.posts[0]?.thumbnail
                ? asset(s.posts[0].thumbnail)
                : asset(photos[6]),
              "Browse references",
            ],
            [
              "script",
              "film",
              "Production board",
              media(
                typeof s.film.storyboard === "string"
                  ? s.film.storyboard
                  : s.film.storyboard?.path,
              ) || asset(photos[4]),
              "Review shots",
            ],
            [
              "statics",
              "image",
              "Creative assets",
              media(asList(cre.statics)[0]?.path) || asset(photos[5]),
              "View artwork",
            ],
          ].map(([to, icon, title, img, action]) => (
            <button
              key={to}
              className={"workspace-card " + to}
              onClick={() => go(to)}
            >
              <div className="workspace-image">
                {img && <img alt="" src={img} />}
                <span>
                  <Icon name={icon} />
                </span>
              </div>
              <div>
                <h3>{title}</h3>
                <span>
                  {action} <Icon name="arrow" size={14} />
                </span>
              </div>
            </button>
          ))}
        </div>
      </Section>
      {s.posts.length > 0 && (
        <Section
          title="Research references"
          action={
            <button className="link" onClick={() => go("swipe")}>
              View swipe file <Icon name="arrow" />
            </button>
          }
        >
          <div className="reference-list">
            {s.posts.slice(0, 4).map((p) => (
              <button key={p.id} onClick={() => enter(p.id)}>
                {p.thumbnail && <img src={asset(p.thumbnail)} alt="" />}
                <div>
                  <small>
                    {p.platform} · {p.creator}
                  </small>
                  <strong>{p.title}</strong>
                </div>
                {p.outlier_ratio != null && (
                  <Badge mode="good">
                    {Number(p.outlier_ratio).toFixed(1)}× baseline
                  </Badge>
                )}
                <Icon name="arrow" />
              </button>
            ))}
          </div>
        </Section>
      )}
    </>
  );
}
function Lineage({ s, inspect, go, enter }) {
  const b = s.brief,
    c = s.creative,
    script = c.script || {},
    shots = asList(script.shots);
  const node = (title, obj, kind, fn) => (
    <button
      key={String(obj.id || title)}
      onClick={
        fn ||
        (() =>
          inspect({
            title,
            inputs: obj.insight_ref || obj.post_ids || obj.url,
            output: obj,
            recipe: obj.recipe || kind,
            checks: obj.checks || obj.evidence,
          }))
      }
    >
      <small>{kind}</small>
      <span>{title}</span>
      <Icon name="northeast" size={13} />
    </button>
  );
  return (
    <Section title="Trace each shot">
      {shots.length ? (
        shots.map((shot, i) => {
          const fact =
            b.claim_sources?.find((f) => f.id === shot.insight_ref) ||
            b.strengths?.find((r) => r.id === shot.insight_ref);
          const pattern = s.patterns.find((p) => p.id === shot.pattern_ref);
          const concept =
            s.concepts.find(
              (c) => c.id === (s.selected.concept_id || script.concept_id),
            ) || s.concepts[0];
          return (
            <div key={shot.id || i} className="lineage-row">
              {fact
                ? node(fact.text || fact.title, fact, "Source fact")
                : node(shot.insight_ref || "Product brief", b, "Insight")}
              {pattern && node(pattern.name, pattern, "Pattern")}
              {concept && node(concept.title, concept, "Concept")}
              {node(
                shot.vo || shot.vo_line || shot.visual,
                shot,
                "Script · shot " + (i + 1),
              )}
              {node("Inspect frame", shot, "Frame", () => {
                const line = s.creative.lineage?.find((l) => l.to === shot.id);
                const film = s.film.hero || s.film.variants?.[0];
                const samples = film?.measured_preflight?.samples || [];
                const target = shot.start + Math.min(0.25, shot.duration / 2);
                const rendered = samples.find(
                  (f) => Math.abs(f.time - target) < 0.03,
                );
                const path = rendered?.path || line?.frame;
                const delivered = film?.shots?.find(
                  (v) => v.shot_id === shot.id,
                );
                inspect({
                  title: "Shot " + (i + 1) + " frame",
                  inputs: [shot.insight_ref, shot.pattern_ref],
                  recipe: shot.visual,
                  output: {
                    file: path,
                    source: rendered
                      ? "Decoded from master"
                      : "Storyboard reference",
                    delivered: delivered?.delivered_visual,
                    deviation: delivered?.visual_deviation,
                  },
                  preview: path && (
                    <img
                      className="wide-img"
                      src={urlFor(s.id, path, s.selected.directory || "")}
                      alt={"Shot " + (i + 1)}
                    />
                  ),
                  checks: shot.checks || script.judge?.status,
                });
              })}
            </div>
          );
        })
      ) : (
        <Empty>Produce a concept to trace the evidence behind each shot.</Empty>
      )}
      {s.patterns.map((p) => (
        <div key={p.id} className="lineage-row">
          {node(p.name, p, "Pattern")}
          {asList(p.post_ids).map((id) => {
            const source = s.posts.find((x) => x.id === id);
            return (
              source &&
              node(source.title, source, "Research frame", () => enter(id))
            );
          })}
        </div>
      ))}
    </Section>
  );
}
export default function Studio({ first, initialId, initialView }) {
  const [s, setState] = useState(first),
    [run, setRun] = useState(initialId),
    [view, setView] = useState(titles[initialView] ? initialView : "overview"),
    [runList, setRuns] = useState([]),
    [products, setProducts] = useState([]),
    [item, setItem] = useState(null),
    [dialog, setDialog] = useState(""),
    [error, setError] = useState(""),
    [mobile, setMobile] = useState(false),
    [postId, setPost] = useState(""),
    [sourceLink, setSourceLink] = useState(""),
    [handle, setHandle] = useState(""),
    [pending, setPending] = useState(false);
  const current = useRef(run);
  current.current = run;
  const refresh = useCallback(async () => {
    const id = current.current;
    const v = await api("/runs/" + id);
    if (current.current === id) setState(v);
    return v;
  }, []);
  const lists = useCallback(
    () =>
      Promise.all([api("/runs"), api("/products")]).then(([r, p]) => {
        setRuns(r);
        setProducts(p);
      }),
    [],
  );
  useEffect(() => {
    lists().catch((e) => setError(e.message));
    refresh().catch((e) => setError(e.message));
  }, [run, lists, refresh]);
  const job = s?.jobs?.[0],
    busy = pending || job?.status === "running";
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(
      () => refresh().catch((e) => setError(e.message)),
      1500,
    );
    return () => clearInterval(t);
  }, [busy, refresh]);
  useEffect(() => {
    const pop = () => {
      const q = new URLSearchParams(location.search);
      setRun(q.get("run") || initialId);
      setView(titles[q.get("view")] ? q.get("view") : "overview");
    };
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, [initialId]);
  const navigate = (v, id = run) => {
    setView(v);
    setMobile(false);
    setItem(null);
    setDialog("");
    if (id !== run) {
      setState(null);
      setRun(id);
    }
    window.history.pushState(
      null,
      "",
      "?run=" + encodeURIComponent(id) + "&view=" + v,
    );
    window.scrollTo({ top: 0 });
  };
  const enter = (id) => {
    setPost(id);
    navigate("inspect");
  };
  const act = async (action, body = {}) => {
    if (busy) return;
    setPending(true);
    setError("");
    try {
      await post("/runs/" + run + "/" + action, body);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
    }
  };
  const upload = async (files, extra = {}) => {
    try {
      const ids = [];
      for (const f of files) {
        if (files.length > 10 || f.size > 48 * 1024 ** 2)
          throw Error("Select up to ten files of 48 MiB each.");
        const r = await api(
          "/runs/" + run + "/uploads?filename=" + encodeURIComponent(f.name),
          { method: "POST", body: f },
        );
        ids.push(r.id);
      }
      await act("deconstruct", { uploads: ids, ...extra });
    } catch (e) {
      setError(e.message);
    }
  };
  const create = async (e) => {
    e.preventDefault();
    setPending(true);
    try {
      const res = await post("/runs", { handle });
      await lists();
      navigate("overview", res.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
    }
  };
  const asset = (p) => urlFor(run, p),
    media = (p) => urlFor(run, p, s?.selected?.directory || "");
  const shared = {
    s,
    asset,
    media,
    act,
    busy,
    enter,
    inspect: setItem,
    go: navigate,
  };
  const loaders = {
    overview: () => <Overview {...shared} />,
    swipe: () => <Swipe {...shared} upload={upload} sourceLink={sourceLink} />,
    inspect: () => (
      <Inspect
        {...shared}
        postId={postId}
        setPost={setPost}
        attach={(url) => {
          setSourceLink(url);
          navigate("swipe");
        }}
      />
    ),
    patterns: () => <Patterns {...shared} />,
    concepts: () => <Concepts {...shared} />,
    script: () => <Script {...shared} />,
    video: () => (
      <Video
        {...shared}
        quote={async () => {
          try {
            return await api("/film-quote");
          } catch (e) {
            setError(e.message);
            return null;
          }
        }}
      />
    ),
    statics: () => <Statics {...shared} />,
    testing: () => <Testing {...shared} />,
    lineage: () => <Lineage {...shared} />,
  };
  const group = (label, items) => (
    <div className="nav-group">
      <small>{label}</small>
      {items.map(([id, name, icon]) => (
        <button
          key={id}
          className={view === id ? "active" : ""}
          aria-current={view === id ? "page" : undefined}
          onClick={() => navigate(id)}
        >
          <Icon name={icon} />
          {name}
          {id === view && <span className="nav-dot" />}
        </button>
      ))}
    </div>
  );
  return (
    <div className="shell">
      <aside className={"sidebar " + (mobile ? "open" : "")}>
        <button
          className="brand"
          onClick={() => navigate("overview")}
          aria-label="Dot & Key studio overview"
        >
          Dot <i>&</i> Key<span>Content Studio</span>
        </button>
        <div className="nav-wrap">
          {group("Workspace", nav.slice(0, 1))}
          {group("Research", nav.slice(1, 4))}
          {group("Production", nav.slice(4, 8))}
          {group("Performance", nav.slice(8))}
        </div>
        <button className="sidebar-foot" onClick={() => setDialog("runs")}>
          <Icon name="folder" /> Switch campaign <Icon name="chevron" />
        </button>
      </aside>
      {mobile && (
        <button
          className="scrim"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <main>
        <header>
          <div>
            <button
              className="mobile-toggle icon-btn"
              onClick={() => setMobile(!mobile)}
              aria-label="Open navigation"
            >
              <Icon name="menu" />
            </button>
            <span className="breadcrumb">Studio</span>
            <span className="slash">/</span>
            {titles[view]}
          </div>
          <button className="run-select" onClick={() => setDialog("runs")}>
            <span className="live-dot" />
            {s?.meta.title || s?.brief?.product?.category || "Campaign"}
            <Icon name="chevron" size={14} />
          </button>
        </header>
        <div className="content">
          <div className="page-heading">
            <h1>{titles[view]}</h1>
            {view === "overview" && (
              <button className="secondary" onClick={() => setDialog("new")}>
                <Icon name="plus" /> New campaign
              </button>
            )}
          </div>
          {error && (
            <div role="alert" className="notice bad">
              {error}
              <button onClick={() => setError("")}>Dismiss</button>
            </div>
          )}
          {job && job.status !== "complete" && (
            <div role="status" className="notice">
              {job.action} · {job.status}
              {job.error && " · " + job.error}
            </div>
          )}
          {s ? (
            !s.brief?.product && !busy && view === "overview" ? (
              <Empty>
                Product brief unavailable.{" "}
                <button className="link" onClick={() => act("brief")}>
                  Build brief
                </button>
              </Empty>
            ) : (
              loaders[view]()
            )
          ) : (
            <Empty>Loading campaign…</Empty>
          )}
        </div>
      </main>
      {item && (
        <Inspector key={item.title} item={item} close={() => setItem(null)} />
      )}
      {dialog === "runs" && (
        <Modal title="Campaigns" close={() => setDialog("")}>
          <div className="run-list">
            {runList.map((r) => (
              <button key={r.id} onClick={() => navigate("overview", r.id)}>
                <Icon name="folder" />
                <span>
                  {r.title || nice(r.handle)}
                  <small>{r.id}</small>
                </span>
                <Icon name="arrow" />
              </button>
            ))}
          </div>
          <button className="primary" onClick={() => setDialog("new")}>
            <Icon name="plus" /> New campaign
          </button>
        </Modal>
      )}
      {dialog === "new" && (
        <Modal title="New campaign" close={() => setDialog("")}>
          <form onSubmit={create}>
            <label>
              Catalog product
              <select
                required
                value={handle}
                onChange={(e) => setHandle(e.target.value)}
              >
                <option value="">Select a product</option>
                {products.map((p) => (
                  <option value={p.handle} key={p.handle}>
                    {p.title}
                  </option>
                ))}
              </select>
            </label>
            <button disabled={pending || !handle} className="primary">
              Create product brief <Icon name="arrow" />
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
