"use client";
import { useEffect, useRef, useState } from "react";
import {
  VIEWS,
  Mark,
  Sheet,
  label,
  withQuery,
  dateLabel,
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
  categories,
  category,
  asOf,
  run,
  navigate,
  close,
}) {
  const [query, setQuery] = useState(""),
    [answer, setAnswer] = useState(""),
    [cites, setCites] = useState([]),
    [pending, setPending] = useState(false),
    [err, setErr] = useState(""),
    [matches, setMatches] = useState(null),
    [active, setActive] = useState(-1),
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
    if (psearch.length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(
          withQuery("/api/search", {
            q: psearch.slice(0, 180),
            category,
            as_of: asOf,
          }),
          { signal: controller.signal },
        );
        if (!response.ok) throw Error();
        const data = await response.json();
        if (!controller.signal.aborted) setMatches({ ...data, query: psearch });
      } catch {
        if (!controller.signal.aborted)
          setMatches({ error: true, query: psearch });
      }
    }, 180);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [psearch, category, asOf]);
  const found = matches?.query === psearch ? matches : null;
  function fromLink(row) {
    const url = new URL(row.href, location.origin);
    const { view, ...args } = Object.fromEntries(url.searchParams);
    if (url.hash) args.card = decodeURIComponent(url.hash.slice(1));
    return {
      name: row.title,
      icon: view,
      view,
      args,
      section: [row.type ? label(row.type) : "Source", args.category]
        .filter(Boolean)
        .join(" · "),
    };
  }
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
    ...[
      ["video", "Video production"],
      ["swipe", "Research library"],
      ["script", "Script and storyboard"],
      ["kit", "Campaign kit"],
    ].map(([step, name]) => ({
      name,
      icon: "studio",
      section: "Studio",
      view: "studio",
      args: {
        studioStep: step,
        run: run || "watermelon-demo",
        category: run ? category : "Sunscreen",
      },
    })),
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
  options = [...options, ...(found?.results || []).map(fromLink)]
    .filter(
      (a, i, arr) =>
        arr.findIndex(
          (b) =>
            a.name === b.name &&
            JSON.stringify(a.args) === JSON.stringify(b.args) &&
            a.view === b.view,
        ) === i,
    )
    .slice(0, 12);
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
  async function ask(question = query.trim()) {
    if (!question || !onlineForAction()) return;
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
          question,
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
        if (controller.signal.aborted) return;
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
  const isQuestion =
    !command &&
    (/^(what|why|how|who|which|when|where|is|are|does|do|can|should|compare|tell me)\b/i.test(
      q,
    ) ||
      q.endsWith("?"));
  const loading = psearch.length >= 2 && !found;
  const opensResult = active >= 0 || (!isQuestion && options.length > 0);
  function submit(e) {
    e.preventDefault();
    if (pending) return;
    if (opensResult) go(options[active] || options[0]);
    else if (q && !command && (!loading || isQuestion)) ask();
  }
  function edit(value) {
    abort.current?.abort();
    setPending(false);
    setQuery(value);
    setAsked(false);
    setErr("");
    setActive(-1);
  }
  return (
    <Sheet title="Search or ask the market" close={close}>
      <div className="mk-command">
        <form onSubmit={submit} className="mk-command-input">
          <Mark name="search" size={16} />
          <input
            ref={input}
            autoComplete="off"
            maxLength={1500}
            aria-label="Search the workspace or ask a question"
            placeholder="Try a product, a campaign or a question…"
            value={query}
            onChange={(e) => edit(e.target.value)}
            onKeyDown={(e) => {
              if (
                !asked &&
                options.length &&
                ["ArrowUp", "ArrowDown"].includes(e.key)
              ) {
                e.preventDefault();
                const next =
                  e.key === "ArrowDown"
                    ? (active + 1) % options.length
                    : active <= 0
                      ? options.length - 1
                      : active - 1;
                setActive(next);
                list.current?.children[next]?.scrollIntoView({
                  block: "nearest",
                });
              }
            }}
          />
          <button
            disabled={
              pending ||
              (!opensResult && (!q || command || (loading && !isQuestion)))
            }
            aria-label={opensResult ? "Open result" : "Ask question"}
          >
            <Mark name="arrow" />
          </button>
        </form>
        <p className="mk-search-context">
          {asked ? "Answer context" : "Search all saved data"} ·{" "}
          {asked
            ? (found?.categories || [category]).join(" and ")
            : category + " first"}{" "}
          · {dateLabel(asOf)}
        </p>
        {asked ? (
          <div className="mk-answer" aria-live="polite">
            <p>
              {answer ||
                (!err && pending ? "Looking through the saved evidence…" : "")}
            </p>
            {cites.length > 0 && (
              <div className="mk-citations">
                <h3>Sources</h3>
                {cites.map((c, i) => (
                  <button key={c.href} onClick={() => go(fromLink(c))}>
                    <b>{i + 1}</b>
                    {c.title}
                    <Mark name="external" size={13} />
                  </button>
                ))}
              </div>
            )}
            {err && (
              <p role="alert">
                {err}{" "}
                <button className="mk-text-btn" onClick={() => ask()}>
                  Try again
                </button>
              </p>
            )}
            {!pending && (
              <button
                className="mk-text-btn"
                onClick={() => {
                  setAsked(false);
                  input.current?.focus();
                }}
              >
                See search results
              </button>
            )}
          </div>
        ) : (
          <>
            {q && !command && (
              <button className="mk-prompt mk-ask-action" onClick={() => ask()}>
                <Mark name="message" size={16} />
                <span>Answer “{q}” using saved evidence</span>
                <Mark name="arrow" size={14} />
              </button>
            )}
            <div className="mk-command-label">
              {q
                ? "Matching results"
                : recent.length
                  ? "Recent and suggested"
                  : "Jump to a view"}
            </div>
            <div ref={list} className="mk-command-options">
              {options.map((o, i) => (
                <button
                  key={o.view + JSON.stringify(o.args) + o.name}
                  className={
                    active === i || (active < 0 && !isQuestion && i === 0)
                      ? "active"
                      : ""
                  }
                  onClick={() => go(o)}
                >
                  <Mark name={o.icon} size={16} />
                  <span>{o.name}</span>
                  <small>{o.section}</small>
                </button>
              ))}
            </div>
            {loading && <p role="status">Searching saved data…</p>}
            {found?.error && (
              <p role="status">
                Saved data search is unavailable. You can still open views and
                categories.
              </p>
            )}
            {!loading && !found?.error && !options.length && (
              <p>
                No matches. Try a shorter product name or a customer’s exact
                wording.
              </p>
            )}
            {!q && (
              <>
                <div className="mk-command-label">Ask a question</div>
                {[
                  "What do customers complain about?",
                  "What should we do in " + category + "?",
                  "How does demand look for lip balm?",
                ].map((t) => (
                  <button
                    key={t}
                    className="mk-prompt"
                    onClick={() => {
                      edit(t);
                      ask(t);
                    }}
                  >
                    {t}
                    <Mark name="arrow" size={14} />
                  </button>
                ))}
              </>
            )}
          </>
        )}
      </div>
    </Sheet>
  );
}
