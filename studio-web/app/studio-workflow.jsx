"use client";
import { useState } from "react";
import { Badge, Icon } from "./ui";

const steps = [
  ["swipe", "Research"],
  ["inspect", "Deconstruct"],
  ["patterns", "Patterns"],
  ["concepts", "Concepts"],
  ["statics", "Create"],
  ["testing", "Test"],
];
export const outputs = [
  ["statics", "Statics"],
  ["aplus", "A+ content"],
  ["listings", "Listing"],
  ["script", "Script & storyboard"],
  ["video", "Video"],
];
export function Workflow({ s, view, go, open }) {
  const stage = outputs.some(([id]) => id === view)
    ? "statics"
    : view === "overview"
      ? "swipe"
      : view === "kit"
        ? "testing"
        : view;
  const index = steps.findIndex(([id]) => id === stage);
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
            Lineage <Icon name="nodes" size={15} />
          </button>
        </div>
      </div>
      <div className="studio-status">
        <Badge mode={s?.brief.product ? "good" : ""}>
          {s?.brief.product ? "Brief loaded ✓" : "Preparing brief"}
        </Badge>
        {s?.brief?.product && (
          <button className="link" onClick={() => go("overview")}>
            View brief
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
            <span>{String(i + 1).padStart(2, "0")}</span>
            {title}
          </button>
        ))}
      </nav>
      <div className="studio-track">
        <i
          style={{ width: (Math.max(1, index + 1) / steps.length) * 100 + "%" }}
        />
      </div>
      {stage === "statics" && (
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
  const zip = "/studio-api/runs/" + encodeURIComponent(run) + "/kit.zip";
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
        <a className="primary" href={zip} download>
          <Icon name="download" /> Download kit
        </a>
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
