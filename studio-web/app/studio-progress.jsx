"use client";
import { useEffect, useState } from "react";

const destinations = {
  "Product brief": ["overview", "product brief"],
  "Discover posts": ["swipe", "research library"],
  "Deconstruct source": ["inspect", "reference breakdown"],
  "Concept slate": ["concepts", "creative directions"],
  "Generate campaign": ["script", "script and artwork"],
  "Render hero film": ["video", "hero film"],
  "Render draft variants": ["video", "draft videos"],
  "Measure published variant": ["testing", "test results"],
};

export function JobProgress({
  job,
  submitting,
  disconnected,
  view,
  go,
  demo = false,
}) {
  const running = job?.status === "running";
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!running || demo) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running, job?.id, demo]);
  if (!job && !submitting) return null;
  const [dest, output] = destinations[job?.action] || [
    "listings",
    "adapted copy",
  ];
  const work = job?.work || {};
  const elapsed = Math.max(
    0,
    Math.floor((now - Date.parse(job?.created_at)) / 1000),
  );
  const failed = ["failed", "interrupted"].includes(job?.status);
  const history = job?.stages || [];
  const relevant =
    view === dest ||
    (dest === "script" && view === "concepts") ||
    (dest === "inspect" && view === "swipe");
  if (!submitting && !running && !failed && !relevant) return null;
  if (submitting && !running)
    return (
      <div className="job-progress" role="status">
        <i className="studio-spinner" /> {submitting}
      </div>
    );
  const film = job.action.startsWith("Render");
  const phases = film
    ? [
        ["drafts", "Drafts"],
        ...(job.action === "Render hero film"
          ? [
              ["motion", "Motion"],
              ["hero", "Hero edit"],
            ]
          : []),
        ["exports", "Exports"],
        ["checks", "Checks"],
      ]
    : [];
  const phaseIndex = phases.findIndex(([id]) => id === work.phase);
  return (
    <aside
      className={
        "job-progress " +
        (running && !demo ? "running" : failed ? "failed" : "finished")
      }
      aria-label="Production status"
    >
      <div className="job-title">
        <strong>
          {running && <i className="studio-spinner" />}
          {job.action}
        </strong>
        <span>
          {demo
            ? "Walkthrough example"
            : running
              ? Math.floor(elapsed / 60) + "m " + (elapsed % 60) + "s elapsed"
              : failed
                ? "Needs attention"
                : "Complete"}
        </span>
      </div>
      <div role="status" aria-live="polite">
        {running ? (
          <>
            <p>{job.stage}</p>
            {disconnected && (
              <p>Reconnecting to live updates. Showing the last saved stage.</p>
            )}
          </>
        ) : failed ? (
          <p>{job.error || "The operation stopped before completion."}</p>
        ) : (
          <p>
            {dest === "inspect"
              ? "Source processing finished. Open the breakdown for results or media instructions."
              : "Your " + output + " is ready to review."}
          </p>
        )}
      </div>
      {running && phases.length > 0 && (
        <ol className="render-phases" aria-label="Film production phases">
          {phases.map(([id, label], i) => (
            <li
              key={id}
              aria-current={id === work.phase ? "step" : undefined}
              className={i < phaseIndex ? "done" : ""}
            >
              {i < phaseIndex ? "✓ " : ""}
              {label}
            </li>
          ))}
        </ol>
      )}
      {running &&
        (work.total > 0 ? (
          <label className="work-meter">
            {work.completed} of {work.total} {work.unit}
            <progress value={work.completed} max={work.total} />
          </label>
        ) : (
          <progress className="work-meter" aria-label={job.stage} />
        ))}
      {(failed || (!running && dest !== view)) && (
        <button
          className="link"
          onClick={() => go(failed && dest === "inspect" ? "swipe" : dest)}
        >
          {failed ? "Review inputs and retry" : "Open " + output} →
        </button>
      )}
      {history.length > 1 && (
        <details>
          <summary>Activity history</summary>
          <ol className="job-history">
            {history
              .slice()
              .reverse()
              .map((h, i) => (
                <li key={(h.updated_at || "") + i}>
                  <time>
                    {new Date(h.updated_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                  {h.stage}
                </li>
              ))}
          </ol>
        </details>
      )}
    </aside>
  );
}

const sample = [
  ["Preparing draft 1 of 6", "drafts", 0, 6, "drafts ready"],
  [
    "Adding narration and assembling the last draft",
    "drafts",
    5,
    6,
    "drafts ready",
  ],
  ["Motion clip 2 of 2 · generating motion", "motion", 1, 2, "clips ready"],
  [
    "Joining the hero shots and checking sound",
    "hero",
    5,
    5,
    "shots assembled",
  ],
  ["Exporting the Meta feed video", "exports", 2, 3, "platform files ready"],
  [
    "Checking the finished hero and six drafts",
    "checks",
    6,
    7,
    "videos checked",
  ],
  ["Complete", "", 0, 0, ""],
];

export function RenderReplay() {
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing || frame === sample.length - 1) return;
    const timer = setTimeout(() => setFrame(frame + 1), 1900);
    return () => clearTimeout(timer);
  }, [frame, playing]);
  const [stage, phase, completed, total, unit] = sample[frame];
  const done = frame === sample.length - 1;
  return (
    <section className="render-replay" aria-label="Example render timeline">
      <h3>Try the render timeline</h3>
      <p>This example shows the updates you’ll see during a hero render.</p>
      <div className="tour-controls">
        <button
          className="secondary"
          onClick={() => {
            if (done) setFrame(0);
            setPlaying(done || !playing);
          }}
        >
          {done ? "Replay example" : playing ? "Pause example" : "Play example"}
        </button>
        {!done && (
          <button
            className="link"
            onClick={() => {
              setPlaying(false);
              setFrame(frame + 1);
            }}
          >
            Next update →
          </button>
        )}
      </div>
      <JobProgress
        job={{
          action: "Render hero film",
          stage,
          work: { phase, completed, total, unit },
          status: done ? "complete" : "running",
        }}
        view="video"
        demo
      />
    </section>
  );
}
