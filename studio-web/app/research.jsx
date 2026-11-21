"use client";
import { useExampleTyping } from "./guided-tour";
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

export function Swipe({
  s,
  asset,
  act,
  enter,
  upload,
  busy,
  sourceLink,
  tourStep,
}) {
  const [url, setUrl] = useState(sourceLink || ""),
    [platform, setPlatform] = useState(""),
    [brand, setBrand] = useState(""),
    [pattern, setPattern] = useState("");
  const [showAds, setShowAds] = useState(false),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [active, setActive] = useState(false),
    [limit, setLimit] = useState(24);
  const extra = {
    ...(url ? { url } : {}),
    ...(showAds && start
      ? { ad_start: start, ad_end: end || null, ad_active: active }
      : {}),
  };
  const file = useRef(null),
    [sending, setSending] = useState(false);
  const candidates = Array.isArray(s.discovery)
    ? s.discovery
    : s.discovery?.candidates || s.discovery?.posts || [];
  const [search, setSearch] = useState("");
  const searchInput = useRef(null);
  useEffect(() => {
    if (tourStep === "references")
      searchInput.current?.scrollIntoView({ block: "center" });
  }, [tourStep]);
  const stopTyping = useExampleTyping(
    tourStep === "references",
    "deconstruct",
    setSearch,
  );
  const catalog = [...s.posts, ...candidates];
  const owners = [
    ...new Set(
      catalog
        .flatMap((p) => [p.creator, p.brand])
        .filter((x) => typeof x === "string" && x),
    ),
  ].sort();
  const matching = (p) =>
    (!platform || p.platform === platform) &&
    (!brand || [p.creator, p.brand].includes(brand)) &&
    (!pattern ||
      s.patterns.find((x) => x.id === pattern)?.post_ids?.includes(p.id)) &&
    (!search ||
      (p.title + " " + p.creator + " " + p.brand)
        .toLowerCase()
        .includes(search.toLowerCase()));
  const filtered = candidates.filter(matching);
  const available = s.posts.filter(matching);
  return (
    <>
      <Section title="Add a reference">
        <form
          className="action-row"
          onDragOver={(e) => e.preventDefault()}
          onDrop={async (e) => {
            e.preventDefault();
            const files = Array.from(e.dataTransfer.files);
            if (!busy && files.length) {
              setSending(true);
              try {
                await upload(files, extra);
              } finally {
                setSending(false);
              }
            }
          }}
          onSubmit={(e) => {
            e.preventDefault();
            act("deconstruct", extra);
          }}
        >
          <input
            aria-label="Post URL"
            type="url"
            required
            placeholder="Paste a Reel, Short or post URL"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <button className="primary" disabled={busy}>
            Analyze reference <Icon name="arrow" />
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy || sending}
            onClick={() => file.current.click()}
          >
            <Icon name="upload" />
            {sending ? "Uploading…" : "Upload media"}
          </button>
          <input
            hidden
            type="file"
            multiple
            accept=".mp4,.mov,.webm,.jpg,.jpeg,.png,.webp"
            ref={file}
            onChange={async (e) => {
              const files = Array.from(e.target.files);
              if (files.length) {
                setSending(true);
                try {
                  await upload(files, extra);
                } finally {
                  setSending(false);
                  e.target.value = "";
                }
              }
            }}
          />
        </form>
        <details onToggle={(e) => setShowAds(e.currentTarget.open)}>
          <summary>Ad Library dates</summary>
          <div className="filters">
            <label>
              First seen
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label>
              Last active
              <input
                type="date"
                disabled={active}
                value={end}
                min={start}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
            <label>
              <input
                type="checkbox"
                checked={active}
                onChange={(e) => {
                  setActive(e.target.checked);
                  if (e.target.checked) setEnd("");
                }}
              />{" "}
              Still running
            </label>
          </div>
        </details>
      </Section>
      <Section
        title="Analyzed references"
        action={
          <button
            className="secondary"
            onClick={() => act("discover")}
            disabled={busy}
          >
            <Icon name="search" /> Discover posts
          </button>
        }
      >
        <div className="filters">
          <input
            ref={searchInput}
            aria-label="Search references"
            placeholder="Search posts or creators"
            value={search}
            onChange={(e) => {
              stopTyping();
              setSearch(e.target.value);
              setLimit(24);
            }}
          />
          <select
            aria-label="Platform"
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
          >
            <option value="">All platforms</option>
            {[...new Set(catalog.map((p) => p.platform).filter(Boolean))].map(
              (v) => (
                <option key={v}>{v}</option>
              ),
            )}
          </select>
          <select
            aria-label="Brand or creator"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
          >
            <option value="">All creators</option>
            {owners.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
          <select
            aria-label="Pattern"
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
          >
            <option value="">All patterns</option>
            {s.patterns.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        {available.length ? (
          <div className="gallery">
            {available.map((p) => (
              <Card
                key={p.id}
                image={asset(p.thumbnail || p.frames?.[0]?.path)}
                label={p.platform}
                title={p.title || p.creator || "Uploaded source"}
                meta={p.creator}
                onClick={() => enter(p.id)}
              >
                <Badge>
                  {p.outlier_ratio != null
                    ? Number(p.outlier_ratio).toFixed(1) + "× baseline"
                    : nice(p.evidence || p.status)}
                </Badge>
              </Card>
            ))}
          </div>
        ) : (
          <Empty>
            No references match this selection. Paste a link or upload a video
            or carousel.
          </Empty>
        )}
      </Section>
      {candidates.length > 0 && (
        <Section
          title="Discovered posts"
          action={<Badge>{filtered.length} matches</Badge>}
        >
          <div className="gallery discovered">
            {filtered.slice(0, limit).map((p) => (
              <article key={p.id || p.url} className="media-card">
                <a
                  href={p.url}
                  target="_blank"
                  rel="noreferrer"
                  className="discovery-img"
                >
                  {(p.thumbnail || p.thumbnail_url) && (
                    <img
                      loading="lazy"
                      src={asset(p.thumbnail || p.thumbnail_url)}
                      alt={p.creator + " reference"}
                    />
                  )}
                </a>
                <div className="media-body">
                  <small>
                    {p.platform} · {p.creator || p.brand}
                  </small>
                  <h3>{p.title || p.caption || "View post"}</h3>
                  <div className="card-actions">
                    <Badge mode={p.outlier_ratio >= 3 ? "good" : "neutral"}>
                      {p.outlier_ratio != null
                        ? Number(p.outlier_ratio).toFixed(1) + "× baseline"
                        : "Unmeasured"}
                    </Badge>
                    <button
                      className="link"
                      disabled={busy || !p.url}
                      onClick={() => act("deconstruct", { url: p.url })}
                    >
                      Analyze <Icon name="arrow" size={13} />
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
          {filtered.length > limit && (
            <button
              className="secondary more"
              onClick={() => setLimit(limit + 24)}
            >
              Show more posts
            </button>
          )}
        </Section>
      )}
    </>
  );
}
export function Inspect({ s, postId, setPost, asset, inspect, attach }) {
  const p = s.posts.find((p) => p.id === postId) || s.posts[0],
    video = useRef(null),
    [time, setTime] = useState(0);
  if (!p)
    return (
      <Empty>
        Add a source in the research library to inspect its frames and
        transcript.
      </Empty>
    );
  const frames = asList(p.frames),
    frame = frames.reduce(
      (best, f) =>
        Math.abs(f.time - time) < Math.abs((best?.time ?? 1e8) - time)
          ? f
          : best,
      null,
    );
  const jump = (t) => {
    if (Number.isFinite(Number(t))) {
      setTime(+t);
      if (video.current) video.current.currentTime = +t;
    }
  };
  const semantic = Array.isArray(p.semantic)
    ? p.semantic
    : Object.entries(p.semantic || {}).map(([field, v]) => ({
        field,
        ...(typeof v === "object" ? v : { value: v }),
      }));
  return (
    <>
      <div className="action-row">
        <select
          aria-label="Research source"
          value={p.id}
          onChange={(e) => {
            setPost(e.target.value);
            setTime(0);
          }}
        >
          {s.posts.map((post) => (
            <option key={post.id} value={post.id}>
              {post.title || post.id}
            </option>
          ))}
        </select>
        <button
          className="secondary"
          onClick={() =>
            inspect({
              title: p.title || "Source",
              inputs: p.url || p.source,
              recipe: { analysis: p.recipe, model: p.semantic_recipe },
              output: {
                status: p.status,
                duration: p.duration,
                evidence: p.evidence,
              },
              checks: {
                warnings: p.warnings,
                baseline_sample: p.baseline_n,
                first_text: p.first_text_at,
                face_in_first_second: p.face_in_first_second,
                first_product_match: p.first_product_match_at,
                ad_library: p.ad_lifetime,
              },
            })
          }
        >
          Inspect source
        </button>
      </div>
      <div className="split">
        <div className="panel dark-media">
          {p.media && /\.(mp4|mov|webm)$/i.test(p.media) ? (
            <video
              key={p.id}
              ref={video}
              controls
              poster={asset(p.thumbnail)}
              src={asset(p.media)}
              onTimeUpdate={(e) => setTime(e.target.currentTime)}
            />
          ) : frame || p.thumbnail ? (
            <img
              src={asset(frame?.path || p.thumbnail)}
              alt="Selected source frame"
            />
          ) : (
            <Empty>{p.status || "Media unavailable"}</Empty>
          )}
        </div>
        <div className="panel">
          <Badge>{p.platform}</Badge>
          <h2>{p.title || "Uploaded reference"}</h2>
          <p>
            {p.creator}{" "}
            {p.duration != null &&
              " · " + Number(p.duration).toFixed(1) + " seconds"}
          </p>
          <p>{p.evidence}</p>
          {p.status === "upload_required" && (
            <>
              <p>{p.message}</p>
              <button className="secondary" onClick={() => attach(p.url)}>
                Attach original media
              </button>
            </>
          )}
          {p.url && (
            <a href={p.url} rel="noreferrer" target="_blank">
              Original post <Icon name="northeast" />
            </a>
          )}
          {p.status && <p className="muted">{nice(p.status)}</p>}
        </div>
      </div>
      {p.status === "ready" && (
        <Section title="Reference at a glance">
          <div className="panel research-summary">
            {semantic.some((r) => r.field === "hook") && (
              <>
                <h3>How it opens</h3>
                <p>{textOf(semantic.find((r) => r.field === "hook").value)}</p>
              </>
            )}
            {p.duration > 0 && (
              <p>
                {asList(p.shots).length} recorded shots in{" "}
                {Math.round(p.duration)} seconds.
                {p.first_text_at != null && (
                  <>
                    {" "}
                    First on-screen text at{" "}
                    <button
                      className="link"
                      onClick={() => jump(p.first_text_at)}
                    >
                      {p.first_text_at}s
                    </button>
                    .
                  </>
                )}
              </p>
            )}
            {p.outlier_ratio != null && (
              <p>
                {Number(p.outlier_ratio).toFixed(1)}× the creator’s typical
                views, measured against {p.baseline_n || "the available"}{" "}
                reference posts.
              </p>
            )}
          </div>
        </Section>
      )}
      <Section title="Hook & shot frames">
        {frames.length ? (
          <div className="filmstrip">
            {frames.map((f, i) => (
              <button
                key={i}
                onClick={() => jump(f.time)}
                className={frame === f ? "current" : ""}
              >
                <img
                  src={asset(f.path)}
                  alt={"Frame at " + f.time + " seconds"}
                />
                <span>
                  {Number(f.time).toFixed(1)}s {f.hook && " · Hook"}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <Empty>No frames available.</Empty>
        )}
      </Section>
      {frame && p.media_type !== "video" && (
        <Section title="Slide measurements">
          <div className="panel">
            <div className="frame-inspect">
              <img
                src={asset(frame.path)}
                alt="Slide with OCR and face annotations"
              />
              <svg
                viewBox="0 0 1 1"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                {asList(frame.ocr_words).map((o, i) => (
                  <polygon
                    key={i}
                    points={o.box?.map((p) => p.join(",")).join(" ")}
                    fill="none"
                    stroke="#ff538c"
                    strokeWidth=".006"
                  />
                ))}
                {asList(frame.faces).map((q, i) => (
                  <rect
                    key={i}
                    x={q[0]}
                    y={q[1]}
                    width={q[2]}
                    height={q[3]}
                    fill="none"
                    stroke="#60cb84"
                    strokeWidth=".006"
                  />
                ))}
              </svg>
            </div>
            <div className="slide-details">
              <div className="swatches">
                {asList(frame.palette).map((hex, i) => (
                  <i key={i} title={hex} style={{ background: hex }} />
                ))}
              </div>
              <div className="mini-grid" aria-label="Layout brightness">
                {asList(frame.layout_luminance)
                  .flat()
                  .map((l, i) => (
                    <i
                      key={i}
                      style={{
                        background:
                          "rgb(" +
                          Math.round(l * 255) +
                          " " +
                          Math.round(l * 255) +
                          " " +
                          Math.round(l * 255) +
                          ")",
                      }}
                    />
                  ))}
              </div>
              <span>
                {Math.round((frame.text_density || 0) * 100)}% text area ·{" "}
                {frame.face_count || 0} faces
              </span>
            </div>
          </div>
        </Section>
      )}
      {p.ad_lifetime && (
        <div className="panel ad-health">
          <h3>Ad longevity</h3>
          <Data value={p.ad_lifetime} />
        </div>
      )}
      <Section title="Evidence timeline">
        <div className="pair">
          <div className="panel">
            <h3>Transcript</h3>
            {asList(p.transcript).map((t, i) => (
              <button
                className="timeline"
                key={i}
                onClick={() => jump(t.start)}
              >
                <b>{t.start}s</b>
                {t.text}
              </button>
            ))}
            {!asList(p.transcript).length && (
              <p className="muted">No speech transcript available.</p>
            )}
          </div>
          <div className="panel">
            <h3>On-screen text</h3>
            {frames
              .filter((f) => f.ocr?.length)
              .map((f, i) => (
                <button
                  className="timeline"
                  key={i}
                  onClick={() => jump(f.time)}
                >
                  <b>{f.time}s</b>
                  {textOf(f.ocr)}
                </button>
              ))}
          </div>
        </div>
      </Section>
      <Section title="Visual breakdown">
        <div className="panel">
          {semantic.map((v, i) => (
            <div key={i} className="evidence-row">
              <strong>{nice(v.field)}</strong>
              <span>{textOf(v.value)}</span>
              {v.time != null ? (
                <button className="link" onClick={() => jump(v.time)}>
                  {v.time}s
                </button>
              ) : (
                <Badge>Inferred</Badge>
              )}
            </div>
          ))}
          {!semantic.length && (
            <p>No visual interpretation was saved for this reference.</p>
          )}
        </div>
      </Section>
      <Section title="Cuts & audio">
        <div className="panel">
          {p.contact_sheet && (
            <img
              className="wide-img"
              src={asset(p.contact_sheet)}
              alt="Contact sheet showing shot cuts"
            />
          )}
          {(p.audio?.waveform || p.waveform) && (
            <img
              className="wide-img"
              src={asset(p.audio?.waveform || p.waveform)}
              alt="Audio waveform"
            />
          )}
          <Data
            value={{
              cuts: p.cuts,
              audio: Object.fromEntries(
                Object.entries(p.audio || {}).filter(([k]) => k !== "samples"),
              ),
              ad_library: p.ad_lifetime,
            }}
          />
        </div>
      </Section>
    </>
  );
}
export function Patterns({ s, asset, enter, inspect }) {
  return (
    <Section title="Observed formats">
      {s.patterns.length ? (
        s.patterns.map((p) => (
          <article className="panel pattern" key={p.id}>
            <div>
              <Badge>{p.repeatability ?? 0} creators</Badge>
              <h2>{p.name || p.title}</h2>
              <p>
                {p.median_outlier_ratio != null
                  ? Number(p.median_outlier_ratio).toFixed(2) +
                    "× median baseline"
                  : "No measured outlier ratio"}
              </p>
              <button
                className="link"
                onClick={() =>
                  inspect({
                    title: p.name,
                    inputs: p.post_ids,
                    recipe: p.method || "Grouped by format, hook and pacing.",
                    output: p.winning_spec,
                    checks: {
                      support: p.evidence,
                      brand_fit: p.brand_fit,
                      repeatability: p.repeatability,
                    },
                  })
                }
              >
                Winning specification <Icon name="arrow" />
              </button>
            </div>
            <div className="thumbnails">
              {asList(p.post_ids).map((id) => {
                const v = s.posts.find((x) => x.id === id);
                return (
                  v && (
                    <button key={id} title={v.title} onClick={() => enter(id)}>
                      <img
                        src={asset(v.thumbnail || v.frames?.[0]?.path)}
                        alt={v.title}
                      />
                    </button>
                  )
                );
              })}
            </div>
          </article>
        ))
      ) : (
        <Empty>
          Analyze a reference in the research library to see its creative
          patterns.
        </Empty>
      )}
    </Section>
  );
}
