"use client";
import { useState } from "react";
import { Badge, Icon } from "./ui";

const steps = [
  ["overview", "Brief", "Check the product facts and the customer evidence behind this campaign."],
  ["swipe", "References", "Paste a post, upload media or discover examples. You can also continue using the product brief alone."],
  ["inspect", "Breakdown", "Review the opening hook, timing and transcript of your reference."],
  ["patterns", "Patterns", "See which creative techniques appear across the analyzed references."],
  ["concepts", "Concepts", "Generate directions, then produce the one you want to use."],
  ["script", "Script & ads", "Check the words, shot timings and artwork before rendering."],
  ["video", "Video", "Render catalog-photo drafts or a hero with generated motion. Preview the finished files here."],
  ["testing", "Review", "Review the production checks and choose the variants to test."],
  ["kit", "Kit", "Download the campaign files or share a link to this kit."],
];
export const outputs = [["script", "Script & storyboard"], ["statics", "Ads"], ["aplus", "A+ content"], ["listings", "Listing"]];
const stageOf = (view) => outputs.some(([id]) => id === view) ? "script" : view;

export function StepGuide({ s, view, go, act, busy }) {
  const stage = stageOf(view);
  const index = steps.findIndex(([id]) => id === stage);
  if (index < 0 || !s) return null;
  const hasReference = s.posts.some((r) => r.status === "ready");
  let target = steps[index + 1]?.[0];
  let label = target && "Next · " + steps[index + 1][1];
  let operation;
  if (!s.brief.product) { target = "overview"; label = "Build product brief"; operation = "brief"; }
  else if (["swipe", "inspect"].includes(stage) && !hasReference) { target = "concepts"; label = "Continue without a reference"; }
  else if (stage === "concepts" && !s.creative.script) {
    if (!s.concepts.length) { operation = "concepts"; label = "Generate creative directions"; }
    else { target = "choose"; label = "Choose a direction"; }
  }
  else if (index >= 5 && !s.creative.script) { target = "concepts"; label = "Go to creative directions"; }
  else if (stage === "video" && !s.film.video) { operation = "film"; label = "Generate draft videos"; }
  const actNext = () => {
    if (operation) act(operation);
    else if (target === "choose") document.querySelector(".concept .primary")?.focus();
    else go(target);
  };
  return <section className="step-guide" aria-label="Current workflow step">
    <div><small>Step {index + 1} of {steps.length} · {steps[index][1]}</small><p>{steps[index][2]}</p></div>
    <div className="step-actions">
      {index > 0 && <button className="link" onClick={() => go(steps[index - 1][0])}>Back</button>}
      {label && <button className="primary" onClick={actNext} disabled={!!operation && busy}>{label} <Icon name="arrow" size={14}/></button>}
      {stage === "kit" && s.creative.script && <a className="primary" href={"/studio-api/runs/" + s.id + "/kit.zip"} download>Download kit <Icon name="download" size={14}/></a>}
    </div>
  </section>;
}
export function Workflow({ s, view, go, open }) {
  const stage = stageOf(view);
  const ready = {
    overview: s?.brief?.product, swipe: s?.posts?.some((p) => p.status === "ready"), inspect: s?.posts?.some((p) => p.status === "ready"),
    patterns: s?.patterns?.length, concepts: s?.concepts?.length, script: s?.creative?.script, video: s?.film?.video,
    testing: s?.readbacks?.length, kit: s?.creative?.script,
  };
  return (
    <div className="studio-flow">
      <div className="studio-meta">
        <div>
          <span className="eyebrow">Content Studio</span>
          <button className="run-select" onClick={() => open("runs")}>
            {s?.meta.title || s?.brief?.product?.title || "Select campaign"}{" "}
            <Icon name="chevron" size={13} />
          </button>
        </div>
        <div>
          <button onClick={() => open("new")}>New campaign</button>
          <button onClick={() => open("lineage")}>
            Sources <Icon name="nodes" size={15} />
          </button>
        </div>
      </div>
      <div className="studio-status">
        <Badge mode={s?.brief.product ? "good" : ""}>
          {s?.brief.product?.category || "Preparing brief"}
        </Badge>
        {s?.brief?.product && view !== "overview" && (
          <button className="link" onClick={() => go("overview")}>
            Campaign brief
          </button>
        )}
        {s?.brief?.market_evidence && (
          <button className="link" onClick={() => open("source")}>
            Market evidence
          </button>
        )}
      </div>
      <nav
        className="studio-steps"
        data-tour="stepper"
        aria-label="Campaign workflow"
      >
        {steps.map(([id, title], i) => (
          <button
            key={id}
            onClick={() => go(id)}
            aria-current={stage === id ? "step" : undefined}
          >
            <span aria-label={ready[id] ? "Available" : undefined}>{ready[id] ? "✓" : i + 1}</span>
            {title}
          </button>
        ))}
      </nav>
      {stage === "script" && (
        <nav className="studio-create-tabs" aria-label="Creative assets">
          {outputs.map(([id, title]) => (
            <button key={id} aria-pressed={view === id} onClick={() => go(id)}>
              {title}
            </button>
          ))}
        </nav>
      )}
    </div>
  );
}
export function Kit({ s, media, go, run }) {
  const [shared, setShared] = useState("");
  const images = [...(s.creative.statics || []), ...(s.creative.aplus || [])];
  const share = async () => {
    const url = new URL(location.href);
    url.searchParams.set("view", "studio");
    url.searchParams.set("studioStep", "kit");
    url.searchParams.set("run", run);
    try {
      if (navigator.share)
        await navigator.share({
          title: "Dot & Key campaign kit",
          url: url.href,
        });
      else {
        await navigator.clipboard.writeText(url.href);
        setShared("Campaign link copied");
      }
    } catch (e) {
      if (e.name !== "AbortError") setShared(url.href);
    }
  };
  return (
    <section className="studio-kit">
      <div className="kit-heading">
        <div className="kit-spark" aria-hidden="true">
          ✳
        </div>
        <div>
          <span className="eyebrow">{s.creative.script?.title}</span>
          <h2>Campaign kit ready</h2>
          <p>
            {images.length} graphic assets · {s.creative.listings?.length || 0}{" "}
            marketplace listings · {s.film.variants?.length || 0} test films
          </p>
        </div>
      </div>
      <div className="kit-actions">
        <button className="secondary" onClick={share}>
          Share campaign
        </button>
        <button className="link" onClick={() => go("testing")}>
          Review tests
        </button>
      </div>
      {shared && <p role="status">{shared}</p>}
      <div className="gallery">
        {s.film.hero && (
          <article className="panel">
            <video controls preload="metadata" src={media(s.film.hero.video)} />
            <h3>Hero film</h3>
          </article>
        )}
        {images.map((r) => (
          <a className="panel" key={r.id} href={media(r.path)} download>
            <img
              alt={r.label || r.title || r.id}
              src={media(r.path)}
              loading="lazy"
            />
            <h3>{r.label || r.title || r.id}</h3>
          </a>
        ))}
      </div>
    </section>
  );
}
