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

export function JobProgress({ job, submitting, disconnected, view, go }) {
  const running = job?.status === "running";
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!running) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running, job?.id]);
  if (!job && !submitting) return null;
  const [dest, output] = destinations[job?.action] || ["listings", "adapted copy"];
  const work = job?.work || {};
  const elapsed = Math.max(0, Math.floor((now - Date.parse(job?.created_at)) / 1000));
  const failed = ["failed", "interrupted"].includes(job?.status);
  const history = job?.stages || [];
  const relevant = view === dest || (dest === "script" && view === "concepts") || (dest === "inspect" && view === "swipe");
  if (!submitting && !running && !failed && !relevant) return null;
  if (submitting && !running) return <div className="job-progress" role="status"><i className="studio-spinner" /> {submitting}</div>;
  const film = job.action.startsWith("Render");
  const phases = film ? [
    ["drafts", "Drafts"], ...(job.action === "Render hero film" ? [["motion", "Motion"], ["hero", "Hero edit"]] : []),
    ["exports", "Exports"], ["checks", "Checks"],
  ] : [];
  const phaseIndex = phases.findIndex(([id]) => id === work.phase);
  return <aside className={"job-progress " + (running ? "running" : failed ? "failed" : "finished")} aria-label="Production status">
    <div className="job-title"><strong>{running && <i className="studio-spinner"/>}{job.action}</strong>
      <span>{running ? Math.floor(elapsed / 60) + "m " + (elapsed % 60) + "s elapsed" : failed ? "Needs attention" : "Complete"}</span>
    </div>
    <div role="status" aria-live="polite">
      {running ? <><p>{job.stage}</p>{disconnected && <p>Reconnecting to live updates. Showing the last saved stage.</p>}</> :
        failed ? <p>{job.error || "The operation stopped before completion."}</p> :
        <p>{dest === "inspect" ? "Source processing finished. Open the breakdown for results or media instructions." : "Your " + output + " is ready to review."}</p>}
    </div>
    {running && phases.length > 0 && <ol className="render-phases" aria-label="Film production phases">{phases.map(([id, label], i) =>
      <li key={id} aria-current={id === work.phase ? "step" : undefined} className={i < phaseIndex ? "done" : ""}>{i < phaseIndex ? "✓ " : ""}{label}</li>)}</ol>}
    {running && (work.total > 0 ? <label className="work-meter">
      {work.completed} of {work.total} {work.unit}
      <progress value={work.completed} max={work.total}/>
    </label> : <progress className="work-meter" aria-label={job.stage}/>)}
    {(failed || (!running && dest !== view)) && <button className="link" onClick={() => go(failed && dest === "inspect" ? "swipe" : dest)}>
      {failed ? "Review inputs and retry" : "Open " + output} →
    </button>}
    {history.length > 1 && <details><summary>Activity history</summary><ol className="job-history">
      {history.slice().reverse().map((h,i) => <li key={(h.updated_at || "") + i}><time>{new Date(h.updated_at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}</time>{h.stage}</li>)}
    </ol></details>}
  </aside>;
}
