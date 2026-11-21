"use client";
import { useEffect, useRef, useState } from "react";

export const nav = [
  ["overview", "Overview", "grid"],
  ["swipe", "Swipe file", "stack"],
  ["inspect", "Deconstruct", "scan"],
  ["patterns", "Pattern board", "layers"],
  ["concepts", "Concept slate", "spark"],
  ["script", "Script & storyboard", "list"],
  ["video", "Video", "film"],
  ["statics", "Ads & listings", "image"],
  ["testing", "Testing", "chart"],
  ["lineage", "Lineage", "nodes"],
];
const paths = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  stack: "M4 4h13v13H4z M8 20h12V8",
  scan: "M3 8V3h5 M16 3h5v5 M21 16v5h-5 M8 21H3v-5 M6 12h12",
  layers: "m3 8 9-5 9 5-9 5z M3 12l9 5 9-5 M3 16l9 5 9-5",
  spark: "m12 2 2.8 7.2L22 12l-7.2 2.8L12 22l-2.8-7.2L2 12l7.2-2.8z",
  list: "M8 5h13 M8 12h13 M8 19h13 M3 5h.1 M3 12h.1 M3 19h.1",
  film: "M3 4h18v16H3z M3 8h18 M7 4v4 M12 4v4 M17 4v4 M10 11l5 3-5 3z",
  image: "M3 4h18v16H3z M3 17l6-6 5 5 3-3 4 4 M15.5 8h.1",
  chart: "M3 4v16h18 M7 16v-5 M12 16V7 M17 16V9",
  nodes: "M4 10h5v5H4z M15 3h5v5h-5z M15 16h5v5h-5z M9 12h3V6h3 M12 12v6h3",
  arrow: "M4 12h15 M14 6l6 6-6 6",
  northeast: "M5 19 19 5 M7 5h12v12",
  chevron: "m8 10 4 4 4-4",
  plus: "M12 5v14 M5 12h14",
  play: "m8 5 11 7-11 7z",
  x: "m5 5 14 14 M19 5 5 19",
  upload: "M12 16V3 M6 9l6-6 6 6 M4 16v5h16v-5",
  folder: "M3 5h7l2 3h9v12H3z",
  check: "m4 12 5 5L20 6",
  clock: "M12 4a8 8 0 1 0 .01 0 M12 7v5l4 2",
  search: "M10 4a6 6 0 1 0 .1 0 M15 15l5 5",
  menu: "M3 6h18 M3 12h18 M3 18h18",
  file: "M5 2h9l5 5v15H5z M14 2v6h5 M8 13h8 M8 17h6",
  volume: "m3 9 4 0 5-4v14l-5-4H3z M16 8q4 4 0 8",
  download: "M12 3v12 M7 10l5 5 5-5 M4 17v4h16v-4",
};
export function Icon({ name, size = 17 }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name] || paths.file} />
    </svg>
  );
}
export const asList = (x) => (Array.isArray(x) ? x : []);
export const nice = (x) =>
  String(x || "")
    .replaceAll("_", " ")
    .replaceAll("-", " ");
export const textOf = (x) =>
  x == null
    ? "—"
    : typeof x === "object"
      ? x.title || x.label || x.text || x.name || x.quote || JSON.stringify(x)
      : String(x);
export function urlFor(run, path, dir = "") {
  if (!path || typeof path !== "string") return "";
  if (/^https?:\/\//.test(path)) return path;
  if (path.startsWith("/") || path.split("/").includes("..")) return "";
  return (
    "/studio-api/runs/" +
    encodeURIComponent(run) +
    "/assets/" +
    [dir, path]
      .filter(Boolean)
      .join("/")
      .split("/")
      .map(encodeURIComponent)
      .join("/")
  );
}
export function Badge({ children, mode = "" }) {
  return <span className={"badge " + mode}>{children}</span>;
}
export function Section({ title, children, action }) {
  return (
    <section className="section">
      <div className="section-title">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Empty({ children }) {
  return <div className="empty">{children}</div>;
}
export function Data({ value, level = 0 }) {
  if (value == null || value === "")
    return <span className="muted">Unavailable</span>;
  if (typeof value === "boolean")
    return (
      <Badge mode={value ? "good" : "neutral"}>{value ? "Yes" : "No"}</Badge>
    );
  if (typeof value !== "object")
    return typeof value === "string" && /^https?:\/\//.test(value) ? (
      <a target="_blank" rel="noreferrer" href={value}>
        {new URL(value).hostname}
        <Icon size={12} name="northeast" />
      </a>
    ) : (
      <span>{String(value)}</span>
    );
  if (Array.isArray(value))
    return value.length ? (
      <ul className="values">
        {value.map((v, i) => (
          <li key={i}>
            <Data value={v} level={level + 1} />
          </li>
        ))}
      </ul>
    ) : (
      <span className="muted">None recorded</span>
    );
  return (
    <dl className="kv">
      {Object.entries(value).map(([k, v]) => (
        <div key={k}>
          <dt>{nice(k)}</dt>
          <dd>
            {level >= 2 && v && typeof v === "object" ? (
              <details>
                <summary>Inspect</summary>
                <Data value={v} />
              </details>
            ) : (
              <Data value={v} level={level + 1} />
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
export function Modal({ title, close, children, drawer = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    el.showModal();
    return () => el.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={drawer ? "studio-drawer" : undefined}
      aria-label={title}
      onCancel={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="modal-inner">
        <div className="section-title">
          <h2>{title}</h2>
          <button className="icon-btn" aria-label="Close" onClick={close}>
            <Icon name="x" />
          </button>
        </div>
        {children}
      </div>
    </dialog>
  );
}
export function Inspector({ item, close }) {
  const [tab, setTab] = useState("Output");
  return (
    <Modal title={item.title} close={close}>
      <div className="tabs">
        {["Inputs", "Recipe", "Output", "Checks"].map((t) => (
          <button key={t} aria-pressed={t === tab} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      <div className="inspector-body">
        {tab === "Output" && item.preview}
        {item[tab.toLowerCase()] !== undefined ? (
          <Data value={item[tab.toLowerCase()]} />
        ) : (
          <Empty>No {tab.toLowerCase()} recorded for this artifact.</Empty>
        )}
      </div>
    </Modal>
  );
}
export function Card({ image, label, title, meta, onClick, children }) {
  return (
    <button className="media-card" onClick={onClick}>
      {image ? (
        <img src={image} loading="lazy" alt="" />
      ) : (
        <div className="media-placeholder">
          <Icon name="file" size={26} />
        </div>
      )}
      <div className="media-body">
        {label && <small>{label}</small>}
        <h3>{title}</h3>
        {meta && <p>{meta}</p>}
        {children}
      </div>
    </button>
  );
}
