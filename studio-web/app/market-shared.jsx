"use client";
import { useEffect, useRef, useState } from "react";
import { animate, useReducedMotion } from "motion/react";

export const VIEWS = [
  "overview",
  "products",
  "competitors",
  "customers",
  "strategy",
  "studio",
];
export const CATEGORIES = [
  "Sunscreen",
  "Body",
  "Eye",
  "Face Wash",
  "Hair",
  "Lip Balm",
  "Mask",
  "Moisturiser",
  "Serum",
  "Toner",
];
export const label = (value) =>
  String(value ?? "")
    .replaceAll("_", " ")
    .replace(/^./, (s) => s.toUpperCase());
export const number = (n, digits = 0) =>
  n == null || !Number.isFinite(Number(n))
    ? "—"
    : Number(n).toLocaleString("en-IN", { maximumFractionDigits: digits });
export const percent = (n, signed = false) =>
  n == null ? "—" : (signed && n > 0 ? "+" : "") + number(n * 100, 1) + "%";
export const price = (n) => (n == null ? "—" : "₹" + number(n, 2));
export const dateLabel = (
  value,
  opts = { day: "numeric", month: "short", year: "numeric" },
) => {
  const date = new Date((value || "").slice(0, 10) + "T12:00:00Z");
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString("en-GB", { ...opts, timeZone: "UTC" });
};
export const withQuery = (path, values) => {
  const query = new URLSearchParams(
    Object.entries(values).filter(([, v]) => v != null && v !== ""),
  );
  return path + (query.size ? "?" + query : "");
};
const icons = {
  overview:
    "M3 3.5h7.5V11H3z M14 3.5h7V8h-7z M3 14.5h7.5V21H3z M14 11.5h7V21h-7z",
  products: "m4 7 8-4 8 4v10l-8 4-8-4z M4 7l8 4 8-4 M12 11v10 M8 5l8 4",
  competitors: "M3 20V10h5v10 M10 20V4h5v16 M17 20v-7h4v7",
  customers:
    "M15 21v-2a5 5 0 0 0-5-5H8a5 5 0 0 0-5 5v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M17 4a4 4 0 0 1 0 7 M21 21v-2a5 5 0 0 0-3-4.6",
  strategy: "m12 3 7 3-2 10-5 5-5-5L5 6z M9 12l2 2 4-5",
  studio:
    "m12 3 2.1 6.9L21 12l-6.9 2.1L12 21l-2.1-6.9L3 12l6.9-2.1z M19 2v4 M17 4h4",
  chevron: "m8 10 4 4 4-4",
  right: "m9 6 6 6-6 6",
  arrow: "M4 12h16 M14 6l6 6-6 6",
  search: "M16 16l5 5 M18 10.5a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0",
  help: "M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0 M9.5 9a2.6 2.6 0 0 1 5 1c0 1.8-2.5 2.1-2.5 4 M12 17h.01",
  date: "M4 5h16v16H4z M4 10h16 M8 3v4 M16 3v4",
  refresh:
    "M20 5v5h-5 M4 19v-5h5 M19.5 10A7.8 7.8 0 0 0 6 6.8 M4.5 14A7.8 7.8 0 0 0 18 17.2",
  opportunity: "M3 20h18 M5 16v-3 M10 16V9 M15 16V6 M20 16V3",
  share: "M12 3a9 9 0 1 0 9 9h-9z M15 2v7h7a9 9 0 0 0-7-7z",
  demand: "M3 19V5 M3 17h5v-5h5V8h5V4h3",
  velocity: "M3 14h4l3-8 4 13 3-8h4",
  launches:
    "M4 17c3-6 7-11 16-13-.4 9-5 14-12 16l-1-3z M11 13l-1-1 M15 9h.01 M5 15l-2 1 1-5 6-2 M10 19l-1 3 5-2 1-4",
  up: "m5 15 6-6 4 4 6-8 M15 5h6v6",
  sun: "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10 M12 1v3 M12 20v3 M1 12h3 M20 12h3 M4 4l2 2 M18 18l2 2 M4 20l2-2 M18 6l2-2",
  filter: "M3 6h18 M6 12h12 M9 18h6",
  external: "M7 17 18 6 M8 6h10v10",
  enter: "M19 5v9H5 M10 9l-5 5 5 5",
  close: "m6 6 12 12 M18 6 6 18",
  check: "m4 12 5 5L20 6",
  dot: "M12 12h.01",
  message: "M3 4h18v13H9l-5 4v-4H3z M7 8h10 M7 12h6",
  stack: "m3 8 9-5 9 5-9 5z M3 12l9 5 9-5 M3 16l9 5 9-5",
  menu: "M5 12h.01 M12 12h.01 M19 12h.01",
  leaf: "M3 20c2-4 4-7 11-12 M5 16C2 8 9 4 20 3c0 13-7 18-15 13z",
  back: "M20 12H4 M10 6l-6 6 6 6",
  clock: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 6v6l4 2",
  pin: "M9 3h6l-1 6 3 4v1H7v-1l3-4z M12 14v7",
};
export function Mark({ name, size = 18 }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={name === "menu" ? 3 : 1.65}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={icons[name] || icons.stack} />
    </svg>
  );
}
export function Count({ value, digits = 0 }) {
  const ref = useRef(null),
    reduced = useReducedMotion();
  useEffect(() => {
    if (value == null || !ref.current || reduced) return;
    const node = ref.current,
      control = animate(0, Number(value), {
        duration: 0.6,
        ease: "easeOut",
        onUpdate: (n) => {
          node.textContent = n.toLocaleString("en-IN", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
          });
        },
      });
    return () => control.stop();
  }, [value, digits, reduced]);
  return (
    <span ref={ref}>
      {value == null
        ? "—"
        : Number(value).toLocaleString("en-IN", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
          })}
    </span>
  );
}
const cache = new Map(),
  pending = new Map();
export async function loadJSON(path, fresh = false) {
  if (!fresh && cache.has(path)) return cache.get(path);
  if (!fresh && pending.has(path)) return pending.get(path);
  const promise = fetch(path, { headers: { Accept: "application/json" } })
    .then(async (response) => {
      if (!response.ok)
        throw Error("The market service returned " + response.status + ".");
      const data = await response.json();
      cache.set(path, data);
      return data;
    })
    .finally(() => pending.delete(path));
  pending.set(path, promise);
  return promise;
}
export function onlineForAction() {
  if (navigator.onLine) return true;
  window.dispatchEvent(new Event("market:offline"));
  return false;
}
export function invalidate() {
  cache.clear();
  pending.clear();
}
export function useMarketData(path, initial, version = 0) {
  const [state, setState] = useState({
    path,
    data: initial ?? null,
    error: null,
  });
  useEffect(() => {
    if (!path) return;
    let live = true;
    if (initial != null && !version && !cache.has(path))
      cache.set(path, initial);
    setState({ path, data: cache.get(path) ?? null, error: null });
    loadJSON(path)
      .then((data) => live && setState({ path, data, error: null }))
      .catch(
        (err) => live && setState({ path, data: null, error: err.message }),
      );
    return () => {
      live = false;
    };
  }, [path, version, initial]);
  return state.path === path
    ? state
    : { path, data: cache.get(path) ?? null, error: null };
}
export function Status({ error, retry }) {
  return error ? (
    <div className="mk-notice" role="alert">
      <strong>Market data unavailable</strong>
      <p>{error}</p>
      <button className="mk-button" onClick={retry}>
        Try again
      </button>
    </div>
  ) : (
    <div
      aria-busy="true"
      aria-label="Loading market data"
      className="mk-skeleton-grid"
    >
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div key={i} className="mk-skeleton">
          <i />
          <i />
          <i />
        </div>
      ))}
    </div>
  );
}
export function Facts({ rows, caption }) {
  return (
    <table className="mk-sr">
      <caption>{caption}</caption>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {r.map((c, j) =>
              j === 0 ? (
                <th key={j} scope="row">
                  {c}
                </th>
              ) : (
                <td key={j}>{c}</td>
              ),
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
export function Sheet({ title, children, close, wide = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    el.showModal();
    return () => el.close();
  }, []);
  return (
    <dialog
      className={"mk-dialog" + (wide ? " mk-wide-dialog" : "")}
      ref={ref}
      aria-label={title}
      onCancel={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="mk-dialog-inner">
        <header>
          <h2>{title}</h2>
          <button className="mk-icon" onClick={close} aria-label="Close">
            <Mark name="close" />
          </button>
        </header>
        {children}
      </div>
    </dialog>
  );
}
