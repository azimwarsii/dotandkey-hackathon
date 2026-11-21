"use client";
import { useEffect, useRef, useState } from "react";
import {
  VIEWS,
  Mark,
  Sheet,
  label,
  withQuery,
  loadJSON,
  onlineForAction,
} from "./market-shared";

const normal = (s) => s.toLowerCase().replace(/[^a-z0-9]/g, "");
function fuzzy(value, query) {
  const a = normal(value),
    b = normal(query);
  if (a.includes(b)) return true;
  let i = 0;
  for (const c of a) if (c === b[i]) i++;
  return i === b.length;
}
function readRecent() {
  try {
    return JSON.parse(localStorage.getItem("market-recent") || "[]").slice(
      0,
      3,
    );
  } catch {
    return [];
  }
}
export default function MarketCommand({
  mode: initialMode,
  categories,
  category,
  asOf,
  navigate,
  close,
}) {
  const [mode, setMode] = useState(initialMode),
    [query, setQuery] = useState(""),
    [answer, setAnswer] = useState(""),
    [cites, setCites] = useState([]),
    [pending, setPending] = useState(false),
    [err, setErr] = useState(""),
    [hits, setHits] = useState([]),
    [active, setActive] = useState(0),
    [recent, setRecent] = useState([]),
    [asked, setAsked] = useState(false);
  const abort = useRef(null),
    input = useRef(null),
    list = useRef(null);
  useEffect(() => {
    setRecent(readRecent());
    input.current?.focus();
    return () => abort.current?.abort();
  }, []);
  const command = query.trim().startsWith("/"),
    q = query.replace(/^\s*\//, "").trim(),
    psearch = q.replace(/^product\s+/i, "");
  useEffect(() => {
    setActive(0);
    setHits([]);
    let live = true;
    if (psearch.length < 2) return;
    const timer = setTimeout(
      () =>
        loadJSON(withQuery("/api/products", { q: psearch }))
          .then((d) => {
            if (live) setHits((d.products || []).slice(0, 8));
          })
          .catch(() => {}),
      160,
    );
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [psearch]);
  const actions = [
    ...VIEWS.map((v) => ({
      name: label(v),
      icon: v,
      section: "View",
      view: v,
    })),
    {
      name: "SWOT",
      icon: "strategy",
      section: "Strategy",
      view: "strategy",
      args: { card: "swot" },
    },
    ...categories.map((c) => ({
      name: c,
      icon: "stack",
      section: "Category",
      view: "overview",
      args: { category: c },
    })),
  ];
  let options = q
    ? actions.filter((a) => fuzzy(a.name, q))
    : [
        ...recent,
        ...actions.filter(
          (a) =>
            ["products", "competitors", "strategy"].includes(a.view) && !a.args,
        ),
      ];
  options = [
    ...options,
    ...hits.map((p) => ({
      name: p.title,
      icon: "products",
      section: p.category,
      view: "products",
      args: { category: p.category, product: p.handle },
    })),
  ]
    .filter(
      (a, i, arr) =>
        arr.findIndex((b) => a.name === b.name && a.section === b.section) ===
        i,
    )
    .slice(0, 9);
  function go(item) {
    try {
      localStorage.setItem(
        "market-recent",
        JSON.stringify(
          [item, ...recent.filter((r) => r.name !== item.name)].slice(0, 3),
        ),
      );
    } catch {}
    close();
    navigate(item.view, item.args || {});
  }
  async function ask() {
    if (pending || !query.trim() || !onlineForAction()) return;
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setPending(true);
    setAsked(true);
    setAnswer("");
    setErr("");
    setCites([]);
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          category,
          as_of: asOf || undefined,
          question: query.trim(),
        }),
        signal: controller.signal,
      });
      if (!response.ok)
        throw Error("The market service returned " + response.status + ".");
      const reader = response.body.getReader(),
        decoder = new TextDecoder();
      let buffer = "",
        doneEvent = false;
      function process(block) {
        const raw = block
          .split(/\r?\n/)
          .filter((l) => l.startsWith("data:"))
          .map((l) => l.slice(5).trimStart())
          .join("\n");
        if (!raw) return;
        const msg = JSON.parse(raw);
        if (msg.type === "token") setAnswer((s) => s + msg.text);
        if (msg.type === "citations") setCites(msg.citations || []);
        if (msg.type === "done") doneEvent = true;
        if (msg.type === "error")
          throw Error(
            msg.message || msg.detail || "The question could not be answered.",
          );
      }
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const pieces = buffer.split(/\r?\n\r?\n/);
        buffer = pieces.pop() || "";
        pieces.forEach(process);
        if (done) {
          if (buffer.trim()) process(buffer);
          break;
        }
      }
      if (!doneEvent)
        throw Error("The answer stream ended early. Please retry.");
    } catch (e) {
      if (e.name !== "AbortError") setErr(e.message);
    } finally {
      if (!controller.signal.aborted) setPending(false);
    }
  }
  function submit(e) {
    e.preventDefault();
    if (mode === "ask" && !command) {
      ask();
      return;
    }
    if (options[active]) go(options[active]);
    else if (command && /^product\s+/i.test(q)) {
      close();
      navigate("products", { q: psearch });
    }
  }
  function citation(c) {
    const u = new URL(c.href || "/", location.origin);
    const view =
      u.searchParams.get("view") || u.pathname.replace(/^\//, "") || "strategy";
    close();
    navigate(view, {
      category: u.searchParams.get("category") || category,
      as_of: u.searchParams.get("as_of") || asOf,
      card: c.id || decodeURIComponent(u.hash.slice(1)),
    });
  }
  function change(m) {
    abort.current?.abort();
    setMode(m);
    setPending(false);
    setAsked(false);
    setErr("");
    input.current?.focus();
  }
  const searching = mode === "search" || command;
  return (
    <Sheet
      title={mode === "ask" ? "Ask the market" : "Search the workspace"}
      close={close}
    >
      <div className="mk-command">
        <div className="mk-command-tabs">
          <button
            aria-pressed={mode === "search"}
            onClick={() => change("search")}
          >
            <Mark name="search" size={14} />
            Search
          </button>
          <button aria-pressed={mode === "ask"} onClick={() => change("ask")}>
            <Mark name="studio" size={14} />
            Ask the market
          </button>
        </div>
        <form onSubmit={submit} className="mk-command-input">
          <input
            ref={input}
            autoComplete="off"
            aria-label={
              mode === "ask"
                ? "Market question"
                : "Search views, categories and products"
            }
            placeholder={
              mode === "ask"
                ? "Ask about " + category.toLowerCase() + "…"
                : "Search a product, category or view…"
            }
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setAsked(false);
              setErr("");
            }}
            onKeyDown={(e) => {
              if (
                searching &&
                options.length &&
                ["ArrowUp", "ArrowDown"].includes(e.key)
              ) {
                e.preventDefault();
                const next =
                  (active + (e.key === "ArrowDown" ? 1 : -1) + options.length) %
                  options.length;
                setActive(next);
                list.current?.children[next]?.scrollIntoView({
                  block: "nearest",
                });
              }
            }}
          />
          <button
            disabled={pending}
            aria-label={searching ? "Open result" : "Ask question"}
          >
            <Mark name="arrow" />
          </button>
        </form>
        {searching ? (
          <>
            <div className="mk-command-label">
              {q
                ? "Results"
                : recent.length
                  ? "Recent and suggested"
                  : "Suggested views"}
            </div>
            <div ref={list} className="mk-command-options">
              {options.map((o, i) => (
                <button
                  className={active === i ? "active" : ""}
                  onMouseEnter={() => setActive(i)}
                  key={o.name + o.section}
                  onClick={() => go(o)}
                >
                  <Mark name={o.icon} size={16} />
                  <span>{o.name}</span>
                  <small>{o.section}</small>
                </button>
              ))}
              {!options.length && <p>No matching view, category or product.</p>}
            </div>
          </>
        ) : asked ? (
          <div className="mk-answer" aria-live="polite">
            <p>
              {answer ||
                (!err && pending ? "Reading the category evidence…" : "")}
            </p>
            {cites.length > 0 && (
              <div className="mk-citations">
                <h3>Sources</h3>
                {cites.map((c, i) => (
                  <button key={c.id} onClick={() => citation(c)}>
                    <b>{i + 1}</b>
                    {c.title}
                    <Mark name="external" size={13} />
                  </button>
                ))}
              </div>
            )}
            {err && <p role="alert">{err}</p>}
          </div>
        ) : (
          <>
            <div className="mk-command-label">Explore {category}</div>
            {[
              "What are the biggest gaps?",
              "How does demand look?",
              "What do customers complain about?",
            ].map((t) => (
              <button
                key={t}
                className="mk-prompt"
                onClick={() => {
                  setQuery(t);
                  input.current?.focus();
                }}
              >
                {t}
                <Mark name="up" size={15} />
              </button>
            ))}
            <div className="mk-shortcuts">
              {["/competitors", "/swot", "/product watermelon"].map((t) => (
                <button
                  key={t}
                  onClick={() => {
                    setQuery(t);
                    input.current?.focus();
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </Sheet>
  );
}
