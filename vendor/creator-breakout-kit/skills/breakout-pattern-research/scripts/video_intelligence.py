#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import ssl
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
SCRAPECREATORS_BASE = "https://api.scrapecreators.com"
OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-3-flash-preview"
DEFAULT_MAX_VIDEO_MB = 20


def load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_json(path):
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def load_required_key(name):
    load_dotenv(ROOT / ".env")
    key = os.getenv(name)
    if key:
        return key
    raise RuntimeError(f"{name} not found. Add it to creator-breakout-kit/.env or export it in your shell.")


def fetch_json(url, headers=None, timeout=30):
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=timeout, context=ssl_context()) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_json_with_retry(url, headers=None, timeout=30, retries=3, backoff=3):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            return fetch_json(url, headers=headers, timeout=timeout)
        except Exception as error:
            last_error = error
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise last_error


def fetch_bytes(url, max_bytes, timeout=45):
    if not url or max_bytes <= 0:
        return b""
    req = Request(url, headers={"User-Agent": "creator-breakout-kit/1.0"})
    with urlopen(req, timeout=timeout, context=ssl_context()) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            return b""
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        return b""
    return data


def first_url(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        candidates = value.get("url_list") or value.get("urls") or []
        if candidates:
            return candidates[0]
        return value.get("url") or ""
    if isinstance(value, list) and value:
        return first_url(value[0])
    return ""


def transcript_text(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text") or item.get("sentence") or item.get("content") or "")
        return " ".join(part for part in parts if part)
    if isinstance(value, dict):
        return value.get("text") or value.get("transcript") or value.get("content") or ""
    return ""


def supported_image_url(url):
    clean = (url or "").split("?", 1)[0].lower()
    return clean.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))


def video_data_url(video_url, max_bytes):
    data = fetch_bytes(video_url, max_bytes)
    if not data:
        return ""
    return "data:video/mp4;base64," + base64.b64encode(data).decode("ascii")


def detect_platform(video_url):
    url = (video_url or "").lower()
    if "tiktok.com" in url:
        return "tiktok"
    if "instagram.com" in url:
        return "instagram"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    return None


def scrape_tiktok(video_url, api_key):
    data = fetch_json_with_retry(
        f"{SCRAPECREATORS_BASE}/v2/tiktok/video?{urlencode({'url': video_url, 'trim': 'true', 'get_transcript': 'true'})}",
        {"x-api-key": api_key, "User-Agent": "creator-breakout-kit/1.0"},
    )
    item = data.get("aweme_detail") or data.get("itemInfo", {}).get("itemStruct") or {}
    stats = item.get("statistics") or item.get("stats", {})
    video = item.get("video", {})
    author = item.get("author") or {}
    subtitles = [
        sub.get("Url") or sub.get("url")
        for sub in video.get("subtitleInfos", [])
        if (sub.get("Url") or sub.get("url")) and (sub.get("LanguageCodeName") or sub.get("language_code") or "").startswith("en")
    ]
    return {
        "description": item.get("desc", ""),
        "duration": int(video.get("duration", 0) or 0),
        "cover_url": first_url(video.get("cover") or video.get("origin_cover")),
        "play_url": first_url(video.get("play_addr") or video.get("playAddr") or video.get("download_addr")),
        "views": stats.get("play_count") or stats.get("playCount") or 0,
        "likes": stats.get("digg_count") or stats.get("diggCount") or 0,
        "comments": stats.get("comment_count") or stats.get("commentCount") or 0,
        "shares": stats.get("share_count") or stats.get("shareCount") or 0,
        "author": author.get("unique_id") or author.get("uniqueId") or author.get("nickname") or "",
        "author_followers": author.get("follower_count") or item.get("authorStats", {}).get("followerCount") or 0,
        "subtitle_url": subtitles[0] if subtitles else "",
        "transcript": transcript_text(data.get("transcript")),
        "hashtags": [
            tag.get("hashtag_name") or tag.get("hashtagName") or ""
            for tag in item.get("text_extra") or item.get("textExtra", [])
            if tag.get("hashtag_name") or tag.get("hashtagName")
        ],
    }


def scrape_instagram(video_url, api_key):
    data = fetch_json_with_retry(
        f"{SCRAPECREATORS_BASE}/v1/instagram/post?url={quote(video_url, safe='')}",
        {"x-api-key": api_key, "User-Agent": "creator-breakout-kit/1.0"},
    )
    media = data["data"]["xdt_shortcode_media"]
    owner = media.get("owner", {})
    caption_edges = media.get("edge_media_to_caption", {}).get("edges", [])
    caption = caption_edges[0]["node"].get("text", "") if caption_edges else ""
    return {
        "description": caption,
        "duration": media.get("video_duration", 0),
        "cover_url": media.get("display_url", ""),
        "play_url": media.get("video_url", ""),
        "views": media.get("video_view_count") or media.get("video_play_count") or 0,
        "likes": media.get("edge_media_preview_like", {}).get("count", 0),
        "comments": media.get("edge_media_to_comment", {}).get("count") or 0,
        "shares": 0,
        "author": owner.get("username", ""),
        "author_followers": owner.get("edge_followed_by", {}).get("count", 0),
        "subtitle_url": "",
        "hashtags": [word.lstrip("#") for word in caption.split() if word.startswith("#")],
    }


def fetch_transcript(subtitle_url):
    if not subtitle_url:
        return ""
    try:
        req = Request(subtitle_url, headers={"User-Agent": "creator-breakout-kit/1.0"})
        with urlopen(req, timeout=15, context=ssl_context()) as response:
            content = response.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""

    lines = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT"):
            continue
        if re.match(r"^\d+$", line) or re.match(r"[\d:.]+ --> [\d:.]+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line:
            lines.append(line)

    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return " ".join(deduped[:250])


def scrape_video(video_url, api_key):
    platform = detect_platform(video_url)
    if platform == "tiktok":
        meta = scrape_tiktok(video_url, api_key)
    elif platform == "instagram":
        meta = scrape_instagram(video_url, api_key)
    else:
        raise RuntimeError(f"Unsupported Content DNA platform for {video_url}. Supported: TikTok and Instagram.")
    meta["platform"] = platform
    return meta


def prompt_for_video(meta, video_url, niche, transcript):
    views = int(meta.get("views", 0) or 0)
    comments = int(meta.get("comments", 0) or 0)
    comment_rate = f"{comments / views * 100:.2f}%" if views > 0 else "n/a"
    transcript_line = f"- Transcript: {transcript}" if transcript else "- Transcript: not available"
    return f"""Analyze this social video for a creator strategy team. Return ONLY a valid JSON object.

Known evidence:
- Niche/category: {niche}
- Creator: @{meta.get('author', '')} ({meta.get('author_followers', 0):,} followers)
- Description/caption: {meta.get('description', '')}
- Duration: {meta.get('duration', 0)} seconds
- Views: {views:,}
- Likes: {meta.get('likes', 0):,}
- Comments: {comments:,} (comment rate: {comment_rate})
- Shares: {meta.get('shares', 0):,}
- Hashtags: {', '.join(meta.get('hashtags', []) or [])}
- URL: {video_url}
{transcript_line}

You may use the cover image if provided. Do not claim certainty about frame-by-frame action unless supported by transcript, caption, or cover image.

Return this JSON shape:
{{
  "topic": "high-level topic",
  "angle": "specific take or promise",
  "hook_structure": {{
    "visual_hook": "what appears visually in the first 1-3 seconds if knowable, else state uncertainty",
    "text_on_screen": "known or inferred text overlay, else unknown",
    "spoken_line": "first spoken line from transcript/caption, else unknown"
  }},
  "story_structure": ["Beat 1: ...", "Beat 2: ...", "Beat 3: ..."],
  "visual_format": "talking head / b-roll montage / screen text / product demo / unknown",
  "visual_format_confidence": "high / medium / low",
  "key_visuals": ["known or inferred visual 1", "known or inferred visual 2"],
  "audio": {{
    "vo_style": "voice delivery if knowable",
    "pacing": "fast/medium/slow/unknown",
    "music": "known/unknown",
    "sound_design": "known/unknown"
  }},
  "performance_analysis": {{
    "primary_driver": "most likely driver of view count",
    "engagement_type": "debate / utility / inspiration / entertainment / FOMO",
    "why_comments_are_high": "specific reason or 'not enough comment signal'"
  }},
  "brick_name": "short label for reusable mechanic",
  "brick_definition": "what the reusable mechanic is",
  "why_it_worked": "tight explanation grounded in available evidence",
  "portable_bricks": [
    {{
      "brick": "name",
      "description": "2-3 sentence mechanical description",
      "portability": "high / medium / low",
      "reason": "why it transfers"
    }}
  ],
  "plain_english_takeaway": "Use this when...",
  "evidence_quality": {{
    "has_transcript": {str(bool(transcript)).lower()},
    "has_cover_image": {str(bool(meta.get('cover_url'))).lower()},
    "has_video_asset_url": {str(bool(meta.get('play_url'))).lower()},
    "limitations": ["no frame-by-frame analysis unless explicitly visible from cover/transcript", "visual claims should be treated as inferred unless marked high confidence"]
  }}
}}"""


def model_content(meta, video_url, niche, transcript, inline_video_url=""):
    content = [{"type": "text", "text": prompt_for_video(meta, video_url, niche, transcript)}]
    if inline_video_url:
        content.append({"type": "video_url", "videoUrl": {"url": inline_video_url}})
    elif supported_image_url(meta.get("cover_url")):
        content.append({"type": "image_url", "image_url": {"url": meta["cover_url"]}})
    return content


def call_gemini(openrouter_key, model, meta, video_url, niche, transcript, inline_video_url=""):
    content = model_content(meta, video_url, niche, transcript, inline_video_url=inline_video_url)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "response_format": {"type": "json_object"},
    }
    req = Request(
        OPENROUTER_BASE,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://creator-breakout-kit.local",
            "X-Title": "Creator Breakout Kit Video Intelligence",
        },
    )
    try:
        with urlopen(req, timeout=90, context=ssl_context()) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter API error {error.code}: {body}") from error
    return result["choices"][0]["message"]["content"]


def parse_model_json(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(raw)


def post_candidates(kit):
    virlo = kit.get("research", {}).get("virlo", {})
    posts = virlo.get("promoted_source_posts") or virlo.get("videos") or []
    candidates = []
    seen = set()
    for post in posts:
        url = post.get("url") or post.get("post_url")
        if not url or url in seen:
            continue
        platform = detect_platform(url)
        if platform not in {"tiktok", "instagram"}:
            continue
        seen.add(url)
        candidates.append(post)
    return candidates


def analyze_post(post, scrape_key, openrouter_key, model, niche, max_video_bytes=0):
    url = post.get("url") or post.get("post_url")
    meta = scrape_video(url, scrape_key)
    transcript = meta.get("transcript") or fetch_transcript(meta.get("subtitle_url"))
    inline_video_url = video_data_url(meta.get("play_url"), max_video_bytes)
    raw = call_gemini(openrouter_key, model, meta, url, niche, transcript, inline_video_url=inline_video_url)
    dna = parse_model_json(raw)
    video_asset_sent = bool(inline_video_url)
    dna["_meta"] = {
        "source_url": url,
        "platform": meta.get("platform"),
        "creator": f"@{meta.get('author', '')}" if meta.get("author") else post.get("creator", ""),
        "creator_url": post.get("creator", ""),
        "views": meta.get("views") or post.get("views"),
        "likes": meta.get("likes") or post.get("likes"),
        "comments": meta.get("comments") or post.get("comments"),
        "shares": meta.get("shares"),
        "duration_sec": meta.get("duration"),
        "outlier_ratio": post.get("outlier_ratio"),
        "cover_url": meta.get("cover_url"),
        "cover_image_sent_to_model": supported_image_url(meta.get("cover_url")) and not video_asset_sent,
        "play_url_present": bool(meta.get("play_url")),
        "video_asset_sent_to_model": video_asset_sent,
        "transcript_present": bool(transcript),
        "analysis_method": "scrapecreators_video_asset_transcript_metadata_plus_gemini" if video_asset_sent else "scrapecreators_metadata_transcript_cover_plus_gemini",
        "analysis_model": model,
    }
    return dna


def write_markdown(path, analyses):
    lines = ["# Video Intelligence", ""]
    for idx, item in enumerate(analyses, start=1):
        meta = item.get("_meta", {})
        lines += [
            f"## {idx}. {meta.get('source_url', '')}",
            f"- Creator: {meta.get('creator', '')}",
            f"- Views: {meta.get('views', 0)}",
            f"- Outlier ratio: {meta.get('outlier_ratio', '')}",
            f"- Transcript present: {meta.get('transcript_present')}",
            f"- Method: {meta.get('analysis_method')}",
            f"- Topic: {item.get('topic', '')}",
            f"- Angle: {item.get('angle', '')}",
            f"- Visual format: {item.get('visual_format', '')} ({item.get('visual_format_confidence', '')})",
            f"- Brick: {item.get('brick_name', '')}",
            f"- Takeaway: {item.get('plain_english_takeaway', '')}",
            "",
        ]
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--niche", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-video-mb", type=int, default=DEFAULT_MAX_VIDEO_MB)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    load_dotenv(ROOT / ".env")
    kit = load_json(run_dir / "breakout-kit.json")
    if not kit:
        raise SystemExit("breakout-kit.json not found")

    scrape_key = load_required_key("SCRAPECREATORS_API_KEY")
    openrouter_key = load_required_key("OPENROUTER_API_KEY")
    niche = args.niche or kit.get("brand", {}).get("product_offer", "") or kit.get("brand", {}).get("name", "")

    analyses = []
    errors = []
    for post in post_candidates(kit)[: args.limit]:
        try:
            analyses.append(analyze_post(
                post,
                scrape_key,
                openrouter_key,
                args.model,
                niche,
                max_video_bytes=args.max_video_mb * 1024 * 1024,
            ))
        except Exception as error:
            errors.append({
                "url": post.get("url") or post.get("post_url"),
                "error": str(error),
            })

    output = {
        "method": "scrapecreators_metadata_transcript_cover_plus_gemini",
        "model": args.model,
        "coverage": {
            "requested_limit": args.limit,
            "analyzed_count": len(analyses),
            "error_count": len(errors),
            "transcript_count": sum(1 for item in analyses if item.get("_meta", {}).get("transcript_present")),
            "video_asset_count": sum(1 for item in analyses if item.get("_meta", {}).get("video_asset_sent_to_model")),
            "cover_image_count": sum(1 for item in analyses if item.get("_meta", {}).get("cover_image_sent_to_model")),
        },
        "errors": errors,
        "analyses": analyses,
    }
    json_path = run_dir / "video-intelligence.json"
    md_path = run_dir / "video-intelligence.md"
    write_json(json_path, output)
    write_markdown(md_path, analyses)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "analyzed_count": len(analyses)}))


if __name__ == "__main__":
    main()
