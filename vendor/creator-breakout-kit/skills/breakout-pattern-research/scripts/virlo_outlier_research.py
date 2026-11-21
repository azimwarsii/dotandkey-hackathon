#!/usr/bin/env python3
import argparse
import json
import os
import re
import ssl
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
VIRLO_BASE = "https://api.virlo.ai"


def load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def load_virlo_key():
    load_dotenv(ROOT / ".env")
    key = os.getenv("VIRLO_API_KEY")
    if key:
        return key
    raise RuntimeError("VIRLO_API_KEY not found. Add it to creator-breakout-kit/.env or export it in your shell.")


def parse_csv(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def virlo_api(method, path, payload=None, query=None):
    key = load_virlo_key()
    if query:
        query_string = urlencode({k: v for k, v in query.items() if v not in (None, "")})
        if query_string:
            path = f"{path}?{query_string}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{VIRLO_BASE}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "creator-breakout-kit/1.0",
        },
        method=method,
    )
    try:
        with urlopen(req, timeout=60, context=ssl_context()) as resp:
            if resp.status == 204:
                return {}
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
            message = parsed.get("message") or parsed.get("error") or body
        except json.JSONDecodeError:
            message = body
        raise RuntimeError(f"Virlo API error {e.code}: {message}") from e


def safe_slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def find_existing_comet(comets_path, name):
    if not os.path.exists(comets_path):
        return None
    with open(comets_path) as f:
        data = json.load(f)
    for c in data.get("comets", []):
        if c.get("name") == name and c.get("id"):
            return c.get("id")
    return None


def save_comet(comets_path, comet_id, name):
    if not comets_path:
        return
    path = Path(comets_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        data = json.loads(path.read_text())
    else:
        data = {"comets": []}
    comets = data.setdefault("comets", [])
    if not any(c.get("id") == comet_id for c in comets):
        comets.append({"id": comet_id, "name": name})
    path.write_text(json.dumps(data, indent=2))


def create_comet(name, keywords, platforms, min_views, time_range, cadence="daily", exclude_keywords=None):
    payload = {
        "name": name,
        "keywords": parse_csv(keywords),
        "platforms": parse_csv(platforms),
        "cadence": cadence,
        "min_views": min_views,
        "time_range": time_range,
        "meta_ads_enabled": False,
        "is_active": True,
    }
    excluded = parse_csv(exclude_keywords)
    if excluded:
        payload["exclude_keywords"] = excluded

    response = virlo_api("POST", "/v1/comet", payload=payload)
    data = response.get("data", {})
    comet_id = data.get("id")
    if not comet_id:
        raise RuntimeError(f"Could not parse comet id from Virlo response: {response}")
    return comet_id, data


def niche_keywords(niche):
    if not niche:
        return set()
    expansions = {
        "ai": ["artificial intelligence", "chatgpt", "gpt", "claude", "llm", "machine learning", "generative", "prompt", "automation", "agent", "openai", "anthropic", "gemini"],
        "marketing": ["brand", "campaign", "ads", "advertising", "content strategy", "social media", "growth", "funnel", "conversion", "seo", "engagement", "influencer", "creator economy", "copywriting"],
        "content": ["creator", "video", "post", "hook", "viral", "thumbnail", "editing", "storytelling", "script", "caption", "reel", "short"],
        "saas": ["software", "startup", "product", "subscription", "churn", "onboarding", "pricing"],
        "ecommerce": ["shopify", "dtc", "product", "store", "cart", "conversion", "checkout"],
        "fitness": ["workout", "gym", "exercise", "training", "health", "nutrition", "body"],
        "finance": ["investing", "stocks", "crypto", "money", "wealth", "budget", "portfolio"],
        "tech": ["software", "coding", "developer", "app", "startup", "silicon valley", "tool"],
    }
    words = {w.lower() for w in re.split(r"[\s,/]+", niche) if len(w) > 2}
    keywords = set(words)
    for word in words:
        keywords.update(expansions.get(word, []))
    keywords.add(niche.lower())
    return keywords


def relevance_score(video, keywords):
    if not keywords:
        return 99
    hashtags = video.get("hashtags") or []
    text = f"{video.get('description', '') or ''} {' '.join(str(h) for h in hashtags)}".lower()
    return sum(1 for keyword in keywords if keyword in text)


def normalize_video(video):
    author = video.get("author") or {}
    creator = author.get("username", "")
    platform = video.get("type") or video.get("platform") or "tiktok"
    creator_profile = author.get("url") or author.get("profile_url") or ""
    if not creator_profile and creator:
        if platform == "tiktok":
            creator_profile = f"https://www.tiktok.com/@{creator}"
        elif platform == "instagram":
            creator_profile = f"https://www.instagram.com/{creator}/"
        elif platform == "youtube":
            creator_profile = f"https://www.youtube.com/@{creator}"
    return {
        "url": video.get("url", "") or video.get("video_url", ""),
        "views": video.get("views", 0),
        "likes": video.get("number_of_likes", 0),
        "comments": video.get("number_of_comments", 0),
        "creator": creator,
        "creator_url": creator_profile,
        "outlier_ratio": None,
        "source": "comet_video",
        "publish_date": video.get("publish_date", ""),
        "desc": (video.get("description", "") or "")[:120],
        "platform": platform,
    }


def fetch_video_page(comet_id, limit, page=1, min_views=None, platform=None, order_by=None, sort="desc"):
    query = {
        "limit": limit,
        "page": page,
        "sort": sort,
        "min_views": min_views,
        "platforms": platform,
        "order_by": order_by,
    }
    response = virlo_api("GET", f"/v1/comet/{comet_id}/videos", query=query)
    return response.get("data", {}).get("videos", [])


def fetch_videos(comet_id, niche, limit, min_views=None, platform=None, order_by=None, sort="desc", dedup=True):
    fetch_limit = 100 if dedup or niche else limit
    videos = fetch_video_page(comet_id, fetch_limit, page=1, min_views=min_views, platform=platform, order_by=order_by, sort=sort)
    if dedup or niche:
        try:
            videos += fetch_video_page(comet_id, 100, page=2, min_views=min_views, platform=platform, order_by=order_by, sort=sort)
        except RuntimeError:
            pass

    keywords = niche_keywords(niche)
    seen = set()
    selected = []
    for video in videos:
        author = video.get("author") or {}
        creator = author.get("username", "")
        if dedup and creator:
            if creator in seen:
                continue
            seen.add(creator)
        if niche and relevance_score(video, keywords) < 2:
            continue
        selected.append(normalize_video(video))
        if len(selected) >= limit:
            break
    return selected


def fetch_outliers(comet_id, limit, platform=None):
    query = {
        "limit": limit,
        "order_by": "outlier_ratio",
        "sort": "desc",
        "platform": platform,
    }
    resp = virlo_api("GET", f"/v1/comet/{comet_id}/creators/outliers", query=query)
    return resp.get("data", {}).get("outliers", [])


def write_md(path, brand_name, comet_id, keywords, videos, outliers, status_note):
    with open(path, "w") as f:
        f.write(f"# Virlo Outlier Research — {brand_name}\n\n")
        f.write(f"**Comet ID:** `{comet_id}`\n\n")
        f.write(f"**Keywords:** {keywords}\n\n")
        if status_note:
            f.write(f"> {status_note}\n\n")
        f.write("## Top Source Videos\n")
        if videos:
            for v in videos[:10]:
                f.write(f"- **{v.get('creator','unknown')}** ({v.get('platform','')}) — {v.get('views',0)} views\n")
                if v.get("url"):
                    f.write(f"  - {v['url']}\n")
                if v.get("desc"):
                    f.write(f"  - {v['desc']}\n")
        else:
            f.write("- No videos returned yet.\n")
        f.write("\n## Creator Outliers\n")
        if outliers:
            for o in outliers[:10]:
                creator = o.get("creator", {}) if isinstance(o.get("creator"), dict) else {}
                handle = creator.get("username") or o.get("creator_url", "unknown")
                f.write(f"- **{handle}** — {o.get('outlier_ratio',0)}x outlier ratio\n")
                if o.get("creator_url"):
                    f.write(f"  - {o['creator_url']}\n")
        else:
            f.write("- No outliers returned yet.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand-name", required=True)
    ap.add_argument("--niche", required=True)
    ap.add_argument("--keywords", required=True, help="comma-separated")
    ap.add_argument("--platforms", default="tiktok,instagram,youtube")
    ap.add_argument("--min-views", type=int, default=5000)
    ap.add_argument("--time-range", default="this_week")
    ap.add_argument("--cadence", default="daily")
    ap.add_argument("--exclude-keywords")
    ap.add_argument("--comet-id", help="Use an existing Virlo comet instead of creating one")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    comet_name = f"Creator Breakout Kit - {args.brand_name}"
    comets_path = os.getenv("VIRLO_COMETS_PATH")

    comet_id = args.comet_id or (find_existing_comet(comets_path, comet_name) if comets_path else None)
    create_output = None
    if not comet_id:
        comet_id, create_output = create_comet(
            comet_name,
            args.keywords,
            args.platforms,
            args.min_views,
            args.time_range,
            cadence=args.cadence,
            exclude_keywords=args.exclude_keywords,
        )
        save_comet(comets_path, comet_id, create_output.get("name", comet_name))

    fresh_comet = create_output is not None
    status_note = None
    videos = []
    outliers = []

    if fresh_comet:
        status_note = f"Comet created successfully. Virlo says first results arrive after the next scheduled collection run ({args.cadence}), so this outlier pass is pending rather than failed."
    else:
        try:
            videos = fetch_videos(comet_id, args.niche, args.limit, min_views=args.min_views)
        except Exception as e:
            videos = []
            status_note = f"Videos fetch hit an issue: {e}"

        try:
            outliers = fetch_outliers(comet_id, args.limit)
        except Exception as e:
            outliers = []
            msg = str(e)
            if "403" in msg and not videos:
                status_note = (status_note + " | " if status_note else "") + "Virlo has not exposed outlier data for this comet yet. Treating this as pending collection, not a hard failure."
            else:
                status_note = (status_note + " | " if status_note else "") + f"Outliers fetch hit an issue: {e}"

        if not videos and not outliers and not status_note:
            status_note = "No live data returned yet. This usually means the comet exists, but Virlo has not populated enough collection data for an outlier pass yet."

    result = {
        "brand_name": args.brand_name,
        "niche": args.niche,
        "comet_id": comet_id,
        "keywords": [k.strip() for k in args.keywords.split(",") if k.strip()],
        "platforms": [p.strip() for p in args.platforms.split(",") if p.strip()],
        "videos": videos,
        "outliers": outliers,
        "status_note": status_note,
        "create_output": create_output,
    }

    json_path = os.path.join(args.out_dir, "virlo-outlier-research.json")
    md_path = os.path.join(args.out_dir, "virlo-outlier-research.md")
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2)
    write_md(md_path, args.brand_name, comet_id, args.keywords, videos, outliers, status_note)

    print(json.dumps({
        "json_path": json_path,
        "markdown_path": md_path,
        "comet_id": comet_id,
        "video_count": len(videos),
        "outlier_count": len(outliers),
        "status_note": status_note,
    }))


if __name__ == "__main__":
    main()
