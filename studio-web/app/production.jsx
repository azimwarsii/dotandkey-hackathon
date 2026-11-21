"use client";
import { useEffect, useRef, useState } from "react";
import {
  asList,
  Badge,
  Card,
  Data,
  Empty,
  Icon,
  Section,
  textOf,
  nice,
} from "./ui";

export function Concepts({ s, act, busy, inspect }) {
  const [reference, setReference] = useState("");
  return (
    <Section
      title="Creative directions"
      action={
        <button
          disabled={busy}
          className="secondary"
          onClick={() => act("concepts")}
        >
          <Icon name="spark" /> Generate concepts
        </button>
      }
    >
      <div className="filters">
        <label>
          Reference rhythm{" "}
          <select
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          >
            <option value="">Use concept pacing (16 seconds)</option>
            {s.posts
              .filter((p) => p.duration > 0)
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} · {Math.round(p.duration)}s reference
                </option>
              ))}
          </select>
        </label>
      </div>
      {s.concepts.length ? (
        <div className="concept-grid">
          {s.concepts.map((c, i) => (
            <article key={c.id} className="panel concept">
              <div className="section-title">
                <Badge>{c.creator_style || "Concept"}</Badge>
                {c.id === s.selected?.concept_id && (
                  <Badge mode="good">Selected</Badge>
                )}
              </div>
              <h2>{c.title}</h2>
              <p>{c.angle}</p>
              <div className="concept-evidence">
                <Badge>{c.test_priority} test</Badge>
                {s.patterns
                  .filter((p) => p.id === c.pattern_ref)
                  .map((p) => (
                    <span key={p.id}>
                      {p.median_outlier_ratio != null && (
                        <b>{p.median_outlier_ratio.toFixed(1)}× baseline · </b>
                      )}
                      {p.repeatability} supporting{" "}
                      {p.repeatability === 1 ? "creator" : "creators"}
                    </span>
                  ))}
              </div>
              <dl className="kv">
                <div>
                  <dt>Buyer tension</dt>
                  <dd>{textOf(c.buyer_tension)}</dd>
                </div>
                <div>
                  <dt>Breakout driver</dt>
                  <dd>{textOf(c.breakout_driver)}</dd>
                </div>
              </dl>
              <details>
                <summary>Hooks and filming beats</summary>
                <ul>
                  {asList(c.hooks).map((hook) => (
                    <li key={hook}>{hook}</li>
                  ))}
                </ul>
                <ol>
                  {asList(c.beats).map((beat) => (
                    <li key={beat}>{beat}</li>
                  ))}
                </ol>
              </details>
              <div className="card-actions">
                <button
                  disabled={busy}
                  className="primary"
                  onClick={() =>
                    act("generate", {
                      concept_id: c.id,
                      reference_id: reference || null,
                    })
                  }
                >
                  Produce concept <Icon name="arrow" />
                </button>
                <button
                  className="link"
                  onClick={() =>
                    inspect({
                      title: c.title,
                      inputs: [c.insight_ref, c.pattern_ref],
                      recipe: c.recipe || s.creative?.recipe,
                      output: c,
                      checks: c.checks || c.test_priority,
                    })
                  }
                >
                  Inspect
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Empty>
          Generate concepts from the locked brief and the current pattern board.
        </Empty>
      )}
    </Section>
  );
}
function TranslationReview({ s, act, busy, kind, inspect }) {
  const [language, setLanguage] = useState("hi-IN");
  const locale = s.locales?.[language];
  const ids = new Set(
    (kind === "script" ? s.creative.script?.shots : s.creative.listings)?.map(
      (row) => row.id,
    ),
  );
  const rows = (locale?.lines || []).filter((row) => ids.has(row.asset_id));
  return (
    <Section title="Translation review">
      <div className="filters">
        <label>
          Language{" "}
          <select
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
          >
            <option value="hi-IN">Hindi</option>
            <option value="hi-Latn">Hinglish</option>
          </select>
        </label>
        {!locale && (
          <button
            className="secondary"
            disabled={busy}
            onClick={() => act("localize", { language })}
          >
            Generate translation
          </button>
        )}
      </div>
      {locale && (
        <>
          <p>
            These drafts need bilingual review before publication. Select a line
            to check the backtranslation and source.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>English source</th>
                  <th>{locale.label} draft</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {nice(row.asset_id)} · {nice(row.field)}
                    </td>
                    <td>{row.source}</td>
                    <td lang={language}>
                      {row.translation || nice(row.status)}
                    </td>
                    <td>
                      <button
                        className="link"
                        onClick={() =>
                          inspect({
                            title: nice(row.asset_id) + " · " + nice(row.field),
                            inputs: row.fact_refs.map(
                              (id) =>
                                s.brief.claim_sources?.find(
                                  (fact) => fact.id === id,
                                ) || id,
                            ),
                            recipe: locale.recipe,
                            output: {
                              english: row.source,
                              translation: row.translation,
                              backtranslation: row.backtranslation,
                            },
                            checks: { status: row.status, flags: row.flags },
                          })
                        }
                      >
                        Review line <Icon name="northeast" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Section>
  );
}

export function Script({ s, media, inspect, act, busy }) {
  const c = s.creative,
    script = c.script || {},
    shots = asList(script.shots),
    board = s.film?.director?.image || s.film?.storyboard || c.storyboard;
  if (!shots.length)
    return (
      <Empty>Produce a concept to open its shot list and storyboard.</Empty>
    );
  return (
    <>
      <Section
        title={script.title || "Shot list"}
        action={<Badge>{shots.length} shots</Badge>}
      >
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Shot</th>
                <th>Visual & duration</th>
                <th>On-screen text</th>
                <th>Voice-over</th>
                <th>Provenance</th>
              </tr>
            </thead>
            <tbody>
              {shots.map((v, i) => (
                <tr id={v.id || "shot-" + (i + 1)} key={v.id || i}>
                  <td>{String(i + 1).padStart(2, "0")}</td>
                  <td>
                    <b>{v.duration}s</b>
                    <br />
                    {textOf(v.visual)}
                  </td>
                  <td>{v.text || v.on_screen_text}</td>
                  <td>{v.vo || v.vo_line}</td>
                  <td>
                    <button
                      className="link"
                      onClick={() =>
                        inspect({
                          title: "Shot " + (i + 1),
                          inputs: [
                            ...Object.entries(
                              v.line_refs || { source: v.insight_ref },
                            ).map(([field, id]) => ({
                              field,
                              source:
                                s.brief.claim_sources?.find(
                                  (f) => f.id === id,
                                ) || id,
                            })),
                            s.patterns.find((p) => p.id === v.pattern_ref) ||
                              v.pattern_ref,
                          ],
                          recipe: script.judge,
                          output: v,
                          checks: v.checks || script.checks,
                        })
                      }
                    >
                      Evidence <Icon name="northeast" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      {board && (
        <Section title="Storyboard grid">
          <img
            className="wide-img board"
            src={media(
              typeof board === "string" ? board : board.path || board.grid,
            )}
            alt="Storyboard shot grid"
          />
        </Section>
      )}
      <Section title="Script review">
        {asList(script.judge?.diffs).length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Shot</th>
                  <th>Original line</th>
                  <th>Edited line</th>
                  <th>Editor's reason</th>
                </tr>
              </thead>
              <tbody>
                {script.judge.diffs.map((edit) => (
                  <tr key={edit.shot + "-" + edit.field}>
                    <td>
                      {edit.shot} · {nice(edit.field)}
                    </td>
                    <td>{edit.before}</td>
                    <td>{edit.after}</td>
                    <td>{edit.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="panel">
          <Data
            value={{
              script: script.judge,
              clipforge: s.film?.variants?.find((v) => v.clipforge?.judges)
                ?.clipforge?.judges,
            }}
          />
        </div>
      </Section>
      <TranslationReview {...{ s, act, busy, inspect }} kind="script" />
    </>
  );
}
export function Video({ s, media, act, busy, inspect, go }) {
  const f = s.film,
    [chosen, setChosen] = useState("");
  const [quote, setQuote] = useState(null);
  const [quoteError, setQuoteError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!s.creative.script || f.hero) return;
    const controller = new AbortController();
    setQuoteError(false);
    fetch("/studio-api/film-quote", { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then((d) => {
        if (!controller.signal.aborted) setQuote(d);
      })
      .catch(() => {
        if (!controller.signal.aborted) setQuoteError(true);
      });
    return () => controller.abort();
  }, [s.creative.script?.id, !!f.hero, attempt]);
  const rows = asList(f.variants || f.drafts);
  const pick = rows.find((r) => r.id === chosen) || rows[0];
  const movie = (x) =>
    typeof x === "string" ? x : x?.path || x?.video || x?.mp4 || x?.file;
  const player = useRef(null);
  const selected = chosen === "hero" || (!chosen && f.hero) ? f.hero : pick;
  const file = movie(selected) || movie(f.video);
  const gate = selected?.gate || f.gate;
  const editNotes = asList(selected?.clipforge?.gate?.report?.items)
    .filter((item) => ["warn", "fail"].includes(item.status))
    .flatMap((item) => {
      const problems = asList(item.problems)
        .map((p) => p?.en)
        .filter(Boolean);
      return problems.length ? problems : [item.message?.en].filter(Boolean);
    });
  if (!s.creative.script)
    return (
      <Empty>
        Choose a creative direction and produce its script first.{" "}
        <button className="link" onClick={() => go("concepts")}>
          Open creative directions <Icon name="arrow" />
        </button>
      </Empty>
    );
  return (
    <>
      <div className="action-row">
        <button
          disabled={busy || !s.creative.script}
          className="secondary"
          onClick={() => act("film", { paid: false })}
        >
          <Icon name="film" /> Render free drafts
        </button>
        {!f.hero && (
          <button
            disabled={busy || !quote}
            className="secondary"
            onClick={() =>
              act("film", { paid: true, approved_usd: quote.estimated_usd })
            }
          >
            {quote
              ? "Generate hero · US$" +
                Number(quote.estimated_usd).toFixed(2) +
                " motion"
              : "Generate hero film"}
          </button>
        )}
      </div>
      {!f.hero && (
        <p className="video-cost">
          Drafts animate catalog photos. The hero adds generated motion and
          separately billed narration.
          {quoteError && (
            <>
              {" "}
              Motion pricing unavailable.{" "}
              <button className="link" onClick={() => setAttempt((n) => n + 1)}>
                Retry estimate
              </button>
            </>
          )}
        </p>
      )}
      <Section
        title="Screening room"
        action={
          (f.hero || rows.length > 0) && (
            <select
              aria-label="Video variant"
              value={chosen || (f.hero ? "hero" : pick?.id || "")}
              onChange={(e) => setChosen(e.target.value)}
            >
              {f.hero && <option value="hero">Hero film</option>}
              {rows.map((v, i) => (
                <option key={v.id || i} value={v.id}>
                  {v.title || nice(v.id) || "Variant " + (i + 1)}
                </option>
              ))}
            </select>
          )
        }
      >
        {file ? (
          <div className="screening">
            <video
              ref={player}
              key={file}
              src={media(file)}
              controls
              playsInline
            />
            <aside>
              <h2>
                {selected?.title ||
                  (selected === f.hero ? "Hero film" : "Draft variant")}
              </h2>
              <p>{selected?.format || selected?.engine || f.engine}</p>
              {!!selected?.duration && (
                <p>
                  {Math.round(selected.duration)} seconds
                  {selected.recipe?.narration?.length > 0 &&
                    " · Narration by " + selected.recipe.narration.join(", ")}
                </p>
              )}
              {editNotes.length > 0 && (
                <div className="video-review-notes">
                  <h3>ClipForge edit review</h3>
                  <ul>
                    {editNotes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}
              <a className="secondary" download href={media(file)}>
                <Icon name="download" /> Download film
              </a>
              <button
                className="link"
                onClick={() =>
                  inspect({
                    title: "Production record",
                    inputs: selected?.inputs || s.creative.script?.id,
                    recipe: selected?.recipe || f.recipe,
                    output: selected,
                    checks: selected?.qc || f.qc,
                  })
                }
              >
                Inspect production <Icon name="northeast" />
              </button>
            </aside>
          </div>
        ) : (
          <Empty>
            {busy
              ? "Your preview will appear here when rendering finishes."
              : "Generate draft videos to preview your script."}
          </Empty>
        )}
      </Section>
      {(selected?.contact_sheet || f.contact_sheet) && (
        <Section title="Contact sheet">
          <img
            className="wide-img board"
            alt="Rendered shot contact sheet"
            src={media(movie(selected?.contact_sheet || f.contact_sheet))}
          />
        </Section>
      )}
      {selected?.measured_preflight && (
        <Section
          title="Rendered pre-flight"
          action={
            <Badge>
              {selected.measured_preflight.score}% ·{" "}
              {selected.measured_preflight.measured}/
              {selected.measured_preflight.total} measured
            </Badge>
          }
        >
          <div className="panel">
            {selected.measured_preflight.checks.map((ch) => (
              <button
                className="timeline"
                key={ch.id}
                onClick={() => {
                  if (player.current) {
                    player.current.currentTime = ch.time || 0;
                    player.current.scrollIntoView({ block: "center" });
                  }
                }}
              >
                <Badge mode={ch.status === "pass" ? "good" : "neutral"}>
                  {ch.status}
                </Badge>
                <strong>{ch.label}</strong>
                <span>
                  {textOf(ch.value)} · {ch.time}s
                </span>
              </button>
            ))}
          </div>
        </Section>
      )}
      <Section title="Quality gate">
        <div className="panel">
          {gate ? (
            <>
              <h3>
                {gate.status === "pass"
                  ? "Passed production checks"
                  : gate.status === "warn"
                    ? "Ready for team review"
                    : "Review required"}
              </h3>
              <p>
                Technical checks · {nice(gate.technical_qc)}
                <br />
                Product claims · {nice(gate.claim_guard?.status)}
              </p>
              {gate.commercial_review && <p>{gate.commercial_review}</p>}
              <details>
                <summary>Production checks</summary>
                <Data value={gate} />
              </details>
            </>
          ) : (
            <p>Render a video to see its checks.</p>
          )}
        </div>
      </Section>
      {f.social?.cover && (
        <Section title="Cover & carousel">
          <div className="filmstrip">
            {[f.social.cover, ...asList(f.social.carousel)].map((path, i) => (
              <button
                key={path}
                onClick={() =>
                  inspect({
                    title: i === 0 ? "Film cover" : "Carousel slide " + i,
                    inputs: f.hero?.inputs,
                    recipe: "ClipForge",
                    output: path,
                    preview: (
                      <a download href={media(path)}>
                        <img
                          className="wide-img"
                          alt="Social export"
                          src={media(path)}
                        />
                      </a>
                    ),
                    checks: f.hero?.gate,
                  })
                }
              >
                <img src={media(path)} alt={i === 0 ? "Cover" : "Slide " + i} />
                <span>{i === 0 ? "Cover" : "Slide " + i}</span>
              </button>
            ))}
          </div>
        </Section>
      )}
      <Section title="Platform exports">
        <div className="filters">
          {file &&
            !Object.keys(selected?.exports || f.exports || {}).length && (
              <p>Use Download film above for this version.</p>
            )}
          {Object.entries(selected?.exports || f.exports || {}).map(([k, v]) =>
            movie(v) ? (
              <a className="secondary" key={k} href={media(movie(v))} download>
                <Icon name="download" />
                {nice(v.label || k)}
              </a>
            ) : null,
          )}
        </div>
      </Section>
    </>
  );
}
export function Statics({
  s,
  media,
  inspect,
  act,
  busy,
  initialTab,
  unified = false,
}) {
  const [selection, setTab] = useState("Static ads");
  const tab = initialTab || selection;
  const c = s.creative;
  const rows = tab === "Static ads" ? asList(c.statics) : asList(c.aplus);
  return (
    <>
      {!unified && (
        <div className="tabs">
          {["Static ads", "A+ content", "Listing copy"].map((t) => (
            <button key={t} aria-pressed={t === tab} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </div>
      )}
      {tab === "Listing copy" ? (
        <Section title="Marketplace copy">
          {asList(c.listings).map((r, i) => (
            <article className="panel listing" key={i}>
              <Badge>{r.market || r.marketplace}</Badge>
              <h3>{r.title}</h3>
              <p>{r.description}</p>
              <ul>
                {asList(r.bullets).map((b) => (
                  <li key={textOf(b)}>{textOf(b)}</li>
                ))}
              </ul>
              <button
                className="link"
                onClick={() =>
                  inspect({
                    title: "Listing checks",
                    inputs: s.brief.allowed_claims,
                    recipe: r.recipe,
                    output: r,
                    checks: r.checks,
                  })
                }
              >
                Review keywords & checks <Icon name="arrow" />
              </button>
            </article>
          ))}
          {!asList(c.listings).length && (
            <Empty>Produce a concept to create listing copy.</Empty>
          )}
        </Section>
      ) : (
        <Section title={tab} action={<Badge>{rows.length} assets</Badge>}>
          {rows.length ? (
            <div className="gallery">
              {rows.map((r, i) => (
                <Card
                  key={r.id || i}
                  image={media(r.path)}
                  title={r.label || r.title || nice(r.id)}
                  label={r.size?.join?.(" × ") || r.market}
                  onClick={() =>
                    inspect({
                      title: r.label || r.title || "Asset",
                      inputs: r.inputs || s.brief.product.title,
                      recipe: r.recipe || c.recipe,
                      output: { file: r.path, dimensions: r.size },
                      preview: (
                        <a href={media(r.path)} download>
                          <img
                            className="wide-img"
                            alt={r.label}
                            src={media(r.path)}
                          />
                        </a>
                      ),
                      checks: r.checks,
                    })
                  }
                />
              ))}
            </div>
          ) : (
            <Empty>Produce a concept to render its creative assets.</Empty>
          )}
        </Section>
      )}
      {tab === "Listing copy" && c.listings?.length > 0 && (
        <TranslationReview {...{ s, act, busy, inspect }} kind="listing" />
      )}
    </>
  );
}
export function Testing({ s, act, busy, inspect, go }) {
  const c = s.creative,
    vs = asList(c.variants),
    [id, setId] = useState(""),
    [link, setLink] = useState(""),
    [obs, setObs] = useState({});
  return (
    <>
      <Section title="Variant matrix">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Variant</th>
                <th>Format</th>
                <th>Hook</th>
                <th>Pre-flight</th>
              </tr>
            </thead>
            <tbody>
              {vs.map((v) => (
                <tr key={v.id}>
                  <td>{v.title || nice(v.id)}</td>
                  <td>{nice(v.format)}</td>
                  <td>{textOf(v.hook)}</td>
                  <td>
                    <button
                      className="link"
                      onClick={() =>
                        inspect({
                          title: v.title || v.id,
                          inputs: v.script?.shots?.map((s) => s.id),
                          recipe: v.format,
                          output: v.hook,
                          preview: (
                            <div className="shot-links">
                              {asList((v.preflight || c.checks)?.checks).map(
                                (ch, i) => (
                                  <button
                                    key={i}
                                    className="timeline"
                                    onClick={() => {
                                      go("script");
                                      setTimeout(
                                        () =>
                                          document
                                            .getElementById(ch.shot_ref)
                                            ?.scrollIntoView({
                                              block: "center",
                                            }),
                                        40,
                                      );
                                    }}
                                  >
                                    <Badge
                                      mode={
                                        ch.status === "pass"
                                          ? "good"
                                          : "neutral"
                                      }
                                    >
                                      {ch.status}
                                    </Badge>{" "}
                                    {ch.label} · {ch.shot_ref}
                                  </button>
                                ),
                              )}
                            </div>
                          ),
                          checks: v.preflight || v.checks || c.checks,
                        })
                      }
                    >
                      Checklist <Icon name="arrow" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section title="First three tests">
        <div className="panel">
          <Data value={c.test_plan} />
        </div>
      </Section>
      <Section title="Record live results">
        {vs.length ? (
          <form
            className="panel readback"
            onSubmit={(e) => {
              e.preventDefault();
              act("readback", {
                variant_id: id || vs[0].id,
                url: link,
                observations: Object.fromEntries(
                  Object.entries(obs)
                    .filter(([, v]) => v !== "")
                    .map(([k, v]) => [k, Number(v)]),
                ),
              });
            }}
          >
            <label>
              Variant
              <select
                value={id || vs[0]?.id}
                onChange={(e) => setId(e.target.value)}
              >
                {vs.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.title || nice(v.id)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Published post
              <input
                type="url"
                required
                value={link}
                onChange={(e) => setLink(e.target.value)}
                placeholder="https://…"
              />
            </label>
            <div className="readback-fields">
              {Object.entries({
                impressions: "Impressions",
                views_3s: "3-second views",
                completed_views: "Completed views",
                clicks: "Clicks",
                spend_inr: "Spend (₹)",
                acquisitions: "Acquisitions",
              }).map(([k, l]) => (
                <label key={k}>
                  {l}
                  <input
                    type="number"
                    step={k === "spend_inr" ? "0.01" : "1"}
                    min="0"
                    value={obs[k] || ""}
                    onChange={(e) => setObs({ ...obs, [k]: e.target.value })}
                  />
                </label>
              ))}
            </div>
            <button disabled={busy} className="primary">
              Measure variant <Icon name="arrow" />
            </button>
          </form>
        ) : (
          <Empty>A generated variant is required to record results.</Empty>
        )}
        {s.readbacks.map((x) => (
          <div className="panel" key={x.id}>
            <Data value={x} />
          </div>
        ))}
      </Section>
    </>
  );
}
