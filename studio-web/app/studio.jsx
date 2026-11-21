"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Badge,
  Empty,
  Icon,
  Inspector,
  Modal,
  Section,
  asList,
  nav,
  nice,
  urlFor,
} from "./ui";
import { Swipe, Inspect, Patterns } from "./research";
import { Concepts, Script, Video, Statics, Testing } from "./production";

import ProductPicker from "./product-picker";
import CampaignBrief, { MarketSource } from "./campaign-brief";
import { dateLabel } from "./market-shared";
import { JobProgress, RenderReplay } from "./studio-progress";
import { Workflow, StepGuide, Kit } from "./studio-workflow";

const titles = {
  kit: "Campaign kit",
  aplus: "A+ content",
  listings: "Marketplace listing",
  overview: "Campaign brief",
  swipe: "Research library",
  inspect: "Reference breakdown",
  patterns: "Pattern board",
  concepts: "Concept slate",
  script: "Script & storyboard",
  video: "Video production",
  statics: "Ads & listings",
  testing: "Testing",
  lineage: "Sources and production history",
};
async function api(path, options) {
  if (options?.method === "POST" && !navigator.onLine)
    throw Error(
      "Reconnect to start this job. Saved outputs are available offline.",
    );
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
function Overview({ s, asset, go, enter }) {
  const b = s.brief,
    p = b.product || {},
    photos = asList(p.local_images),
    cre = s.creative;
  const short =
    b.claim_sources?.find((f) => f.kind === "short_name")?.text ||
    p.title ||
    s.meta.handle;
  let next = ["swipe", "Add a research reference"];
  if (s.film.video) next = ["video", "Review campaign video"];
  else if (cre.script) next = ["video", "Generate campaign video"];
  else if (s.concepts.length)
    next = ["concepts", "Choose a creative direction"];
  else if (s.posts.some((row) => row.status === "ready"))
    next = ["concepts", "Develop creative directions"];
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
          <button className="primary" onClick={() => go(next[0])}>
            {next[1]} <Icon name="arrow" />
          </button>
          {cre.script && (
            <button className="link brief-kit" onClick={() => go("kit")}>
              Open campaign kit <Icon name="download" size={14} />
            </button>
          )}
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
      {p.title && <CampaignBrief brief={b} />}
      {s.posts.length > 0 && (
        <Section
          title="Research references"
          action={
            <button className="link" onClick={() => go("swipe")}>
              Open research library <Icon name="arrow" />
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
      {b.market_evidence && (
        <div className="lineage-row">
          {node(b.market_evidence.title, b.market_evidence, "Market evidence")}
          {node(b.product.title, b, "Product brief")}
        </div>
      )}
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
export default function Studio({
  first,
  initialId = "watermelon-demo",
  initialView,
  initialReference,
  tourStep,
  embedded = false,
  onRoute,
}) {
  const [s, setState] = useState(first),
    [run, setRun] = useState(initialId),
    [view, setView] = useState(titles[initialView] ? initialView : "overview"),
    [runList, setRuns] = useState([]),
    [products, setProducts] = useState([]),
    [listState, setListState] = useState("loading"),
    [loadError, setLoadError] = useState(""),
    [item, setItem] = useState(null),
    [dialog, setDialog] = useState(""),
    [error, setError] = useState(""),
    [mobile, setMobile] = useState(false),
    [postId, setPost] = useState(initialReference || ""),
    [sourceLink, setSourceLink] = useState(""),
    [pending, setPending] = useState(false),
    [liveJob, setLiveJob] = useState(null),
    [connectionLost, setConnectionLost] = useState(false),
    [submitting, setSubmitting] = useState("");
  const current = useRef(run);
  current.current = run;
  useEffect(() => {
    if (embedded) setView(titles[initialView] ? initialView : "overview");
  }, [initialView, embedded]);
  useEffect(() => {
    if (initialReference) setPost(initialReference);
  }, [initialReference]);
  const refresh = useCallback(async () => {
    const id = current.current;
    const v = await api("/runs/" + id);
    if (current.current === id) setState(v);
    return v;
  }, []);
  const loadCampaign = useCallback(async () => {
    const id = current.current;
    setLoadError("");
    try {
      await refresh();
    } catch (e) {
      if (current.current === id) setLoadError(e.message);
    }
  }, [refresh]);
  const lists = useCallback(async () => {
    setListState("loading");
    try {
      const [r, p] = await Promise.all([api("/runs"), api("/products")]);
      setRuns(r);
      setProducts(p);
      setListState("ready");
    } catch {
      setListState("failed");
    }
  }, []);
  useEffect(() => {
    lists();
    loadCampaign();
  }, [run, lists, loadCampaign]);
  const job = s?.jobs?.[0],
    busy = pending || job?.status === "running";
  useEffect(() => {
    if (job?.status !== "running") return;
    const path = "/api/jobs/" + encodeURIComponent(job.id);
    let closed = false,
      polling = false;
    const controller = new AbortController();
    const events = new EventSource(
      path + "/events?run=" + encodeURIComponent(run),
    );
    setConnectionLost(false);
    const apply = (update) => {
      if (closed) return;
      setLiveJob((old) => {
        if (old?.id === update.id && old.updated_at > update.updated_at)
          return old;
        const stages =
          old?.id === update.id ? old.stages || [] : job.stages || [];
        const newer =
          !stages.length || update.updated_at > stages.at(-1).updated_at;
        return {
          ...update,
          stages:
            update.stages ||
            (newer
              ? [
                  ...stages,
                  { stage: update.stage, updated_at: update.updated_at },
                ]
              : stages),
        };
      });
      if (["complete", "failed", "interrupted"].includes(update.status)) {
        refresh()
          .then(() => {
            if (!closed) events.close();
          })
          .catch(() => {
            if (!closed) setConnectionLost(true);
          });
      }
    };
    const poll = async () => {
      if (closed || polling) return;
      polling = true;
      try {
        const response = await fetch(path, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw Error();
        const next = await response.json();
        if (!closed) {
          apply(next);
          setConnectionLost(false);
        }
      } catch {
        if (!closed) setConnectionLost(true);
      } finally {
        polling = false;
      }
    };
    events.onmessage = (message) => {
      setConnectionLost(false);
      apply(JSON.parse(message.data));
    };
    events.onerror = () => {
      if (!closed) {
        setConnectionLost(true);
        poll();
      }
    };
    const timer = setInterval(poll, 6500);
    return () => {
      closed = true;
      controller.abort();
      clearInterval(timer);
      events.close();
    };
  }, [job?.id, job?.status, run, refresh]);
  useEffect(() => {
    const pop = () => {
      const q = new URLSearchParams(location.search);
      setRun(q.get("run") || initialId);
      const choice = q.get("studioStep") || q.get("view");
      setView(titles[choice] ? choice : "overview");
    };
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, [initialId, embedded]);
  const navigate = (v, id = run, category, reference) => {
    setError("");
    setView(v);
    setMobile(false);
    setItem(null);
    setDialog("");
    if (id !== run) {
      setState(null);
      setRun(id);
    }
    if (embedded && onRoute) {
      const campaign = runList.find((row) => row.id === id);
      const chosen = products.find((row) => row.handle === campaign?.handle);
      onRoute(
        id,
        v,
        category || chosen?.category || s?.brief?.product?.category,
        reference,
      );
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set("run", id);
    url.searchParams.set("view", embedded ? "studio" : v);
    if (embedded) url.searchParams.set("studioStep", v);
    window.history.pushState(null, "", url);
    window.scrollTo({ top: 0 });
  };
  const enter = (id) => {
    setPost(id);
    navigate("inspect", run, undefined, id);
  };
  const act = async (action, body = {}) => {
    if (busy) return;
    setPending(true);
    setSubmitting(
      "Starting " +
        ({
          film: "video production",
          generate: "campaign production",
          deconstruct: "reference analysis",
          concepts: "concept development",
        }[action] || action) +
        "…",
    );
    setError("");
    try {
      const submitted = await post("/runs/" + run + "/" + action, body);
      if (submitted.status === "running")
        setState(
          (old) =>
            old && {
              ...old,
              jobs: [
                submitted,
                ...old.jobs.filter((j) => j.id !== submitted.id),
              ],
            },
        );
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
      setSubmitting("");
    }
  };
  const upload = async (files, extra = {}) => {
    try {
      const ids = [];
      for (const [index, f] of files.entries()) {
        setSubmitting(
          "Uploading file " + (index + 1) + " of " + files.length + "…",
        );
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
    } finally {
      setSubmitting("");
    }
  };
  const create = async (handle) => {
    setPending(true);
    try {
      const res = await post("/runs", { handle });
      navigate(
        "overview",
        res.id,
        products.find((p) => p.handle === handle)?.category,
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
    }
  };
  const asset = (p) => urlFor(run, p),
    media = (p) => urlFor(run, p, s?.selected?.directory || "");
  const listNotice =
    listState === "loading" ? (
      <div role="status" className="job-progress">
        <i className="studio-spinner" /> Loading campaigns and products…
      </div>
    ) : listState === "failed" ? (
      <div role="alert" className="notice bad">
        Couldn’t load campaigns and products.{" "}
        <button onClick={lists}>Try again</button>
      </div>
    ) : null;
  const shared = {
    s,
    tourStep,
    asset,
    media,
    act,
    busy: busy || !!submitting,
    enter,
    inspect: (value) => {
      setDialog("");
      setItem(value);
    },
    go: navigate,
  };
  const loaders = {
    overview: () => <Overview {...shared} />,
    swipe: () => <Swipe {...shared} upload={upload} sourceLink={sourceLink} />,
    inspect: () => (
      <Inspect
        {...shared}
        postId={postId}
        setPost={enter}
        attach={(url) => {
          setSourceLink(url);
          navigate("swipe");
        }}
      />
    ),
    patterns: () => <Patterns {...shared} />,
    concepts: () => <Concepts {...shared} />,
    script: () => <Script {...shared} />,
    video: () => <Video {...shared} />,
    statics: () => <Statics {...shared} unified={embedded} />,
    aplus: () => <Statics {...shared} unified initialTab="A+ content" />,
    listings: () => <Statics {...shared} unified initialTab="Listing copy" />,
    kit: () =>
      s.creative.script ? (
        <Kit {...shared} run={run} />
      ) : (
        <Empty>Produce a concept to assemble a campaign kit.</Empty>
      ),
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
    <div className={embedded ? "studio-embedded" : "shell"}>
      {!embedded && (
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
      )}
      {mobile && (
        <button
          className="scrim"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="studio-main">
        {embedded ? (
          <Workflow {...{ s, view }} go={navigate} open={setDialog} />
        ) : (
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
        )}
        <div className="content">
          <div className="page-heading">
            <h1>{titles[view]}</h1>
            {view === "overview" && s?.brief?.product && (
              <a
                className="secondary"
                download
                href={"/studio-api/runs/" + run + "/brief.txt"}
              >
                Download brief <Icon name="download" size={14} />
              </a>
            )}
            {view === "overview" && !embedded && (
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
          {s && loadError && (
            <div role="alert" className="notice bad">
              Showing the last saved campaign. Couldn’t refresh its status.
              <button onClick={loadCampaign}>Try again</button>
            </div>
          )}
          <JobProgress
            job={
              liveJob?.id === job?.id && liveJob?.updated_at >= job?.updated_at
                ? liveJob
                : job
            }
            submitting={submitting}
            disconnected={connectionLost}
            view={view}
            go={navigate}
          />
          <StepGuide {...shared} view={view} />
          {tourStep === "video" && view === "video" && <RenderReplay />}
          {s ? (
            !s.brief?.product && busy ? (
              <Empty>{job?.stage || "Preparing the product brief…"}</Empty>
            ) : !s.brief?.product && view === "overview" ? (
              <Empty>
                Product brief unavailable.{" "}
                <button className="link" onClick={() => act("brief")}>
                  Build brief
                </button>
              </Empty>
            ) : (
              loaders[view]()
            )
          ) : loadError ? (
            <div role="alert" className="notice bad">
              Couldn’t open this campaign. {loadError}{" "}
              <button onClick={loadCampaign}>Try again</button>
            </div>
          ) : (
            <div className="job-progress" role="status">
              <i className="studio-spinner" /> Loading campaign brief and saved
              outputs…
            </div>
          )}
        </div>
      </div>
      {item && (
        <Inspector key={item.title} item={item} close={() => setItem(null)} />
      )}
      {dialog === "lineage" && s && (
        <Modal
          title="Sources and production history"
          drawer
          close={() => setDialog("")}
        >
          <Lineage {...shared} />
        </Modal>
      )}
      {dialog === "source" && s?.brief.market_evidence && (
        <Modal title="Market evidence" close={() => setDialog("")}>
          <MarketSource source={s.brief.market_evidence} />
        </Modal>
      )}
      {dialog === "runs" && (
        <Modal title="Campaigns" close={() => setDialog("")}>
          {listNotice}
          <div className="run-list">
            {listState === "ready" && !runList.length && (
              <p>Your first campaign will appear here.</p>
            )}
            {listState === "ready" &&
              runList.map((r) => (
                <button key={r.id} onClick={() => navigate("overview", r.id)}>
                  <Icon name="folder" />
                  <span>
                    {r.title ||
                      products.find((p) => p.handle === r.handle)?.title ||
                      nice(r.handle)}
                    <small>
                      {dateLabel(r.created_at)}
                      {r.evidence?.category && " · " + r.evidence.category}
                    </small>
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
          {error && <p role="alert">{error}</p>}
          {listNotice || (
            <ProductPicker products={products} choose={create} busy={pending} />
          )}
        </Modal>
      )}
    </div>
  );
}
