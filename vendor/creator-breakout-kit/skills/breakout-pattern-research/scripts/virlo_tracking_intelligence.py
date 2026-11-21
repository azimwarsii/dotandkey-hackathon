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
TRACKING_BASE = "https://api.virlo.ai/v1/tracking"


def load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


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


def virlo_tracking_api(method, path, payload=None, query=None):
    key = load_virlo_key()
    if query:
        query_string = urlencode({k: v for k, v in query.items() if v not in (None, "")})
        if query_string:
            path = f"{path}?{query_string}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{TRACKING_BASE}{path}",
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
        raise RuntimeError(f"Virlo Tracking API error {e.code}: {message}") from e


def load_json(path):
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2))


def clean_text(value):
    return " ".join(str(value or "").split())


def platform_from_value(value):
    text = clean_text(value).lower()
    if "tiktok" in text:
        return "tiktok"
    if "instagram" in text or "reels" in text:
        return "instagram"
    if "youtube" in text or "youtu.be" in text:
        return "youtube"
    return ""


def platform_for_source(source):
    return clean_text(source.get("platform")) or platform_from_value(source.get("url")) or platform_from_value(source.get("creator"))


def handle_from_value(value, platform):
    text = clean_text(value)
    if not text:
        return ""
    if text.startswith("@"):
        return text[1:].split("/")[0]
    if text.startswith("http"):
        if platform == "tiktok":
            match = re.search(r"/@([^/?#]+)", text)
            return match.group(1) if match else ""
        if platform == "instagram":
            match = re.search(r"instagram\.com/([^/?#]+)", text)
            return match.group(1) if match else ""
        if platform == "youtube":
            match = re.search(r"youtube\.com/@([^/?#]+)", text)
            return match.group(1) if match else ""
        return ""
    return text.lstrip("@").split("/")[0]


def source_posts_from_virlo(virlo, limit):
    virlo = virlo or {}
    posts = []
    seen = set()

    def add(post, outlier=None):
        outlier = outlier or {}
        url = post.get("url") or post.get("post_url")
        if not url or url in seen:
            return
        seen.add(url)
        platform = platform_for_source(post) or clean_text(outlier.get("platform")) or platform_from_value(url)
        posts.append({
            "url": url,
            "platform": platform,
            "creator": post.get("creator") or post.get("creator_url") or outlier.get("creator_url") or "",
            "title": post.get("title") or post.get("desc") or post.get("description") or "",
            "views": post.get("views") or post.get("view_count"),
            "outlier_ratio": post.get("outlier_ratio") or outlier.get("outlier_ratio"),
        })

    for post in virlo.get("promoted_source_posts", []) or []:
        add(post)
    for post in virlo.get("videos", []) or []:
        add(post)
    for outlier in virlo.get("outliers", []) or []:
        for post in outlier.get("videos", []) or []:
            add(post, outlier)

    return [post for post in posts if post.get("platform") in {"tiktok", "instagram", "youtube"}][:limit]


def target_for_video(post, cadence):
    return {
        "target_type": "video",
        "url": post["url"],
        "platform": post["platform"],
        "scrape_cadence": cadence,
        "source": post,
    }


def target_for_creator(post, cadence):
    platform = post.get("platform")
    creator = clean_text(post.get("creator"))
    if not platform or not creator or creator.lower() == "unknown":
        return None
    target = {
        "target_type": "creator",
        "platform": platform,
        "scrape_cadence": cadence,
        "source": post,
    }
    if creator.startswith("http"):
        target["url"] = creator
    else:
        handle = handle_from_value(creator, platform)
        if not handle:
            return None
        target["handle"] = handle
    return target


def build_targets(virlo, limit=3, cadence="weekly", track="videos"):
    posts = source_posts_from_virlo(virlo, limit)
    targets = []
    for post in posts:
        if track in {"videos", "both"}:
            targets.append(target_for_video(post, cadence))
        if track in {"creators", "both"}:
            creator_target = target_for_creator(post, cadence)
            if creator_target:
                targets.append(creator_target)
    return targets


def list_tracked_videos(platform=None):
    response = virlo_tracking_api("GET", "/videos", query={"limit": 100, "page": 1, "platform": platform})
    return response.get("data", [])


def list_tracked_creators(platform=None):
    response = virlo_tracking_api("GET", "/creators", query={"limit": 100, "page": 1, "platform": platform})
    return response.get("data", [])


def find_tracked_video(target):
    for item in list_tracked_videos(target.get("platform")):
        if clean_text(item.get("url")).rstrip("/") == clean_text(target.get("url")).rstrip("/"):
            return item
    return None


def find_tracked_creator(target):
    handle = target.get("handle") or handle_from_value(target.get("url"), target.get("platform"))
    if not handle:
        return None
    for item in list_tracked_creators(target.get("platform")):
        if clean_text(item.get("platform_handle")).lower().lstrip("@") == handle.lower().lstrip("@"):
            return item
    return None


def start_tracking(target):
    payload = {
        "platform": target["platform"],
        "scrape_cadence": target["scrape_cadence"],
    }
    if target["target_type"] == "video":
        payload["url"] = target["url"]
        if target.get("tracking_account_id"):
            payload["tracking_account_id"] = target["tracking_account_id"]
        return virlo_tracking_api("POST", "/videos", payload=payload).get("data", {})
    if target.get("url"):
        payload["url"] = target["url"]
    else:
        payload["handle"] = target["handle"]
    return virlo_tracking_api("POST", "/creators", payload=payload).get("data", {})


def get_tracked_detail(target_type, tracking_id):
    return virlo_tracking_api("GET", f"/{target_type}s/{tracking_id}").get("data", {})


def get_tracking_report(target_type, tracking_id):
    return virlo_tracking_api("GET", f"/{target_type}s/{tracking_id}/report").get("data", {})


def report_analysis(target_type, report):
    if target_type == "creator":
        report_body = report.get("report") or {}
        return report_body.get("analysis") or {}, report_body.get("created_at", "")
    return report.get("analysis") or {}, report.get("analysis_updated_at", "")


def normalize_notable_comments(comments):
    normalized = []
    for comment in comments or []:
        if isinstance(comment, str):
            normalized.append({"content": clean_text(comment), "likes": None, "insight": ""})
            continue
        normalized.append({
            "content": clean_text(comment.get("content") or comment.get("text")),
            "likes": comment.get("likes"),
            "insight": clean_text(comment.get("insight")),
        })
    return [comment for comment in normalized if comment["content"] or comment["insight"]]


def normalize_audience_sentiment(analysis):
    audience = analysis.get("audience_sentiment")
    if isinstance(audience, dict):
        return {
            "overall_summary": clean_text(audience.get("overall_summary") or audience.get("summary")),
            "sentiment_labels": audience.get("sentiment_labels") or audience.get("labels") or [],
            "notable_comments": normalize_notable_comments(audience.get("notable_comments") or audience.get("comments")),
        }
    if analysis.get("sentiment"):
        return {
            "overall_summary": clean_text(analysis.get("sentiment")),
            "sentiment_labels": [],
            "notable_comments": normalize_notable_comments(analysis.get("notable_comments") or analysis.get("comments")),
        }
    return {
        "overall_summary": "",
        "sentiment_labels": [],
        "notable_comments": [],
    }


def normalize_report(target, tracked, report, created_new=False):
    analysis, analysis_updated_at = report_analysis(target["target_type"], report)
    sentiment = normalize_audience_sentiment(analysis)
    enrichment_status = clean_text(tracked.get("enrichment_status"))
    report_status = "ready" if analysis else "pending"
    return {
        "target_type": target["target_type"],
        "tracking_id": tracked.get("id", ""),
        "created_new_tracking": created_new,
        "status": tracked.get("status", ""),
        "platform": tracked.get("platform") or target.get("platform"),
        "scrape_cadence": tracked.get("scrape_cadence") or target.get("scrape_cadence"),
        "enrichment_status": enrichment_status,
        "report_status": report_status,
        "analysis_updated_at": analysis_updated_at,
        "source_url": target.get("url") or (target.get("source") or {}).get("url", ""),
        "source_creator": (target.get("source") or {}).get("creator", ""),
        "audience_sentiment": sentiment,
        "analysis": analysis,
    }


def tracking_target_key(target):
    if target["target_type"] == "video":
        return f"video:{target.get('platform')}:{clean_text(target.get('url')).rstrip('/')}"
    handle = target.get("handle") or handle_from_value(target.get("url"), target.get("platform"))
    return f"creator:{target.get('platform')}:{handle.lower().lstrip('@')}"


def unique_targets(targets):
    unique = []
    seen = set()
    for target in targets:
        key = tracking_target_key(target)
        if key in seen:
            continue
        seen.add(key)
        unique.append(target)
    return unique


def collect_audience_signals(virlo, limit=3, cadence="weekly", track="videos", create_missing=True):
    targets = unique_targets(build_targets(virlo, limit=limit, cadence=cadence, track=track))
    signals = []
    errors = []
    for target in targets:
        try:
            existing = find_tracked_video(target) if target["target_type"] == "video" else find_tracked_creator(target)
            created_new = False
            if existing:
                tracked = get_tracked_detail(target["target_type"], existing["id"])
            elif create_missing:
                created = start_tracking(target)
                created_new = True
                tracked = get_tracked_detail(target["target_type"], created["id"]) if created.get("id") else created
            else:
                tracked = {}

            if tracked.get("id"):
                report = get_tracking_report(target["target_type"], tracked["id"])
                signals.append(normalize_report(target, tracked, report, created_new=created_new))
            else:
                signals.append(normalize_report(target, {"status": "not_tracked"}, {}, created_new=False))
        except Exception as e:
            errors.append({"target": target, "error": str(e)})

    ready = sum(1 for signal in signals if signal.get("report_status") == "ready")
    return {
        "source": "virlo_tracking",
        "track": track,
        "scrape_cadence": cadence,
        "target_count": len(targets),
        "ready_report_count": ready,
        "pending_report_count": len(signals) - ready,
        "signals": signals,
        "errors": errors,
        "status_note": (
            "Virlo Tracking reports are generated asynchronously; rerun this adapter later to pull pending audience sentiment."
            if signals and ready < len(signals)
            else ""
        ),
    }


def write_md(path, result):
    lines = [
        "# Virlo Audience Signals",
        "",
        f"**Tracking targets:** {result.get('target_count', 0)}",
        f"**Ready reports:** {result.get('ready_report_count', 0)}",
        f"**Pending reports:** {result.get('pending_report_count', 0)}",
        "",
    ]
    if result.get("status_note"):
        lines += [f"> {result['status_note']}", ""]
    for signal in result.get("signals", []):
        sentiment = signal.get("audience_sentiment") or {}
        lines += [
            f"## {signal.get('target_type', 'target').title()} — {signal.get('source_url') or signal.get('source_creator')}",
            f"- Status: {signal.get('report_status')}",
            f"- Enrichment: {signal.get('enrichment_status') or 'unknown'}",
        ]
        if sentiment.get("overall_summary"):
            lines.append(f"- Audience sentiment: {sentiment['overall_summary']}")
        if sentiment.get("sentiment_labels"):
            lines.append(f"- Labels: {', '.join(sentiment['sentiment_labels'])}")
        comments = sentiment.get("notable_comments") or []
        if comments:
            lines.append("- Notable comments:")
            for comment in comments[:5]:
                detail = comment.get("content") or comment.get("insight")
                lines.append(f"  - {detail}")
        lines.append("")
    if result.get("errors"):
        lines += ["## Errors"]
        for error in result["errors"]:
            lines.append(f"- {error.get('error')}")
        lines.append("")
    Path(path).write_text("\n".join(lines).rstrip() + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--research-dir", required=True, help="Directory containing virlo-outlier-research.json")
    ap.add_argument("--out-dir", help="Defaults to --research-dir")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--scrape-cadence", default="weekly", choices=["six_hours", "twelve_hours", "daily", "every_other_day", "weekly"])
    ap.add_argument("--track", default="videos", choices=["videos", "creators", "both"])
    ap.add_argument("--no-create", action="store_true", help="Only fetch existing tracked reports; do not create new tracking records")
    args = ap.parse_args()

    research_dir = Path(args.research_dir)
    out_dir = Path(args.out_dir) if args.out_dir else research_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    virlo = load_json(research_dir / "virlo-outlier-research.json")
    if not virlo:
        raise SystemExit(f"virlo-outlier-research.json not found in {research_dir}")

    result = collect_audience_signals(
        virlo,
        limit=args.limit,
        cadence=args.scrape_cadence,
        track=args.track,
        create_missing=not args.no_create,
    )
    json_path = out_dir / "virlo-audience-signals.json"
    md_path = out_dir / "virlo-audience-signals.md"
    write_json(json_path, result)
    write_md(md_path, result)

    print(json.dumps({
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "target_count": result["target_count"],
        "ready_report_count": result["ready_report_count"],
        "pending_report_count": result["pending_report_count"],
        "status_note": result["status_note"],
    }))


if __name__ == "__main__":
    main()
