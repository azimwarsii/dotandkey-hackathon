"""Public post resolution, observed account baselines and discovery provenance."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from urllib.parse import parse_qs, urlsplit

import httpx

# Handles link to public storefronts or the brand's public social campaign.
ACCOUNTS = {
    "deconstruct": ("deconstruct_skincare", "https://thedeconstruct.in/"),
    "the derma co": ("thedermacoindia", "https://thedermaco.com/"),
    "dr. sheth’s": ("drsheths", "https://www.drsheths.com/"),
    "neutrogena": (
        "neutrogena.india",
        "https://www.neutrogena.in/socialmedia-termsandconditions",
    ),
    "dermdoc": ("dermdoc.in", "https://www.instagram.com/dermdoc.in/"),
    "foxtale": ("foxtaleskin", "https://foxtale.in/"),
    "plum": ("plumgoodness", "https://plumgoodness.com/"),
    "minimalist": ("beminimalist__", "https://beminimalist.co/"),
}
# Verify handle resolution via channels.list before fetching uploads.
CREATORS = (
    "DrAanchalMD",
    "DrManasiSkin",
    "Corallista",
    "ZolieSkinClinic",
    "DrNiveditaDadu",
    "UCj4nEnx8t_HJ5wpL1YPxHaw",
    "UChEKxjma_JAhmACyNjsJSHQ",
    "UCe0K4yVkiHa7DORscY7fk5A",
    "UCcjwEAaBGu1yc89QE3DC1Tw",
    "UCH_RhBu7gVUDictmhfL6DTg",
    "UCc34FvrsixVdHuvaipikMxA",
    "UCdSDwWRfuK3ITxCpCve3blg",
)
BRAND_CHANNELS = {"neutrogena": "UC8l56zCl8EHIrD6EvyjKE7Q"}
LIMIT = 48 * 1024 * 1024


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def uid(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, encoding="utf8", delete=False
    ) as out:
        json.dump(obj, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write("\n")
    os.replace(out.name, path)


def checked_url(url):
    u = urlsplit(str(url))
    if (
        u.scheme not in ("https", "http")
        or u.username
        or u.password
        or u.port not in (None, 80, 443)
    ):
        raise ValueError(
            "Paste a public Instagram, YouTube, TikTok, Facebook or Meta Ad Library post URL."
        )
    host = (u.hostname or "").lower()
    host = re.sub(r"^(?:(?:www|m|mobile)\.)", "", host)
    rules = {
        "instagram.com": ("Instagram", r"^/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)/?$"),
        "youtube.com": ("YouTube", r"^/(?:shorts|live)/([A-Za-z0-9_-]{11})/?$"),
        "youtu.be": ("YouTube", r"^/([A-Za-z0-9_-]{11})/?$"),
        "tiktok.com": ("TikTok", r"^/@[\w.]+/(?:video|photo)/(\d+)/?$"),
        "facebook.com": (
            "Facebook",
            r"^/(?:reel/\d+|[\w.]+/(?:posts|videos)/[\w.]+|share/[rvp]/[\w-]+)/?$",
        ),
        "fb.watch": ("Facebook", r"^/[\w-]+/?$"),
    }
    query = parse_qs(u.query)
    if (
        host == "youtube.com"
        and u.path in ("/watch", "/watch/")
        and re.fullmatch(r"[\w-]{11}", query.get("v", [""])[0])
    ):
        return "YouTube", "https://www.youtube.com/watch?v=" + query["v"][0]
    if (
        host == "facebook.com"
        and u.path.rstrip("/") == "/ads/library"
        and query.get("id", [""])[0].isdigit()
    ):
        return "Meta Ad Library", "https://www.facebook.com/ads/library/?id=" + query[
            "id"
        ][0]
    if host not in rules or not re.fullmatch(rules[host][1], u.path):
        raise ValueError(
            "Unsupported post URL. Paste a direct public post or upload the media."
        )
    platform = rules[host][0]
    if platform == "YouTube":
        return platform, "https://www.youtube.com/watch?v=" + u.path.rstrip("/").split(
            "/"
        )[-1]
    if platform == "Instagram":
        return platform, f"https://www.instagram.com/{u.path.strip('/')}/"
    return platform, f"https://{host}{u.path}"


def _cache(key, fetch, ttl=86400):
    location = Path(
        os.getenv("STUDIO_RESEARCH_CACHE", "data/cache/studio-research")
    ) / (uid(key) + ".json")
    if location.is_file() and time.time() - location.stat().st_mtime < ttl:
        return json.loads(location.read_text())
    data = fetch()
    dump(location, data)
    return data


def _scrape(path, *, fresh=False, **params):
    token = os.getenv("SCRAPECREATORS_API_KEY")
    if not token:
        raise RuntimeError("ScrapeCreators key unavailable")

    def fetch():
        r = httpx.get(
            "https://api.scrapecreators.com" + path,
            params=params,
            headers={"x-api-key": token},
            timeout=35,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("success") is False:
            raise RuntimeError("ScrapeCreators could not retrieve this post")
        return data

    return _cache(
        path + json.dumps(params, sort_keys=True), fetch, ttl=0 if fresh else 86400
    )


def _yt(path, *, fresh=False, **params):
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YouTube Data API key unavailable")

    def fetch():
        r = httpx.get(
            "https://www.googleapis.com/youtube/v3/" + path,
            params=params,
            headers={"X-Goog-Api-Key": key},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    return _cache(
        path + json.dumps(params, sort_keys=True), fetch, ttl=0 if fresh else 86400
    )


def score_account(rows):
    """Compare views against the same creator/platform. Missing counters stay unknown."""
    groups = {}
    for r in rows:
        groups.setdefault((r["platform"], r["creator"]), []).append(r)
    for group in groups.values():
        observed = [
            r["views"]
            for r in group
            if isinstance(r.get("views"), (float, int)) and r["views"] >= 0
        ]
        center = median(observed) if observed else None
        for r in group:
            n = r.get("views")
            ratio = (
                n / center if n is not None and center and len(observed) >= 5 else None
            )
            r.update(
                baseline_n=len(observed),
                baseline_median=center,
                outlier_ratio=round(ratio, 3) if ratio is not None else None,
                evidence="outlier-backed"
                if ratio is not None and ratio >= 3
                else "account-observation",
            )
            for rate, fields in (
                ("comment_rate", ("comments",)),
                ("share_rate", ("shares",)),
                ("engagement_rate", ("likes", "comments")),
            ):
                values = [r.get(k) for k in fields]
                r[rate] = (
                    round(sum(values) / n, 6)
                    if n and all(v is not None for v in values)
                    else None
                )
    return rows


def instagram_account(handle, brand, identity, *, fresh=False):
    rows, cursor = {}, None
    for _ in range(6):
        page = _scrape(
            "/v1/instagram/user/reels",
            handle=handle,
            fresh=fresh,
            **({"max_id": cursor} if cursor else {}),
        )
        for wrapper in page.get("items", []):
            m = wrapper.get("media") or wrapper
            creator = (m.get("user") or {}).get("username", "")
            if creator.casefold() != handle.casefold() or not m.get("code"):
                continue
            url = f"https://www.instagram.com/reel/{m['code']}/"
            caption = (m.get("caption") or {}).get("text", "")
            image = ((m.get("image_versions2") or {}).get("candidates") or [{}])[0].get(
                "url"
            )
            rows[url] = {
                "id": uid(url),
                "url": url,
                "platform": "Instagram",
                "creator": creator,
                "brand": brand,
                "creator_role": "brand",
                "account_source": identity,
                "title": caption.split("\n")[0][:160] or f"{brand} reel",
                "caption": caption[:1500],
                "views": m.get("ig_play_count")
                if m.get("ig_play_count") is not None
                else m.get("play_count"),
                "likes": m.get("like_count"),
                "comments": m.get("comment_count"),
                "shares": m.get("reshare_count"),
                "thumbnail_url": image,
                "duration": m.get("video_duration"),
                "published_at": m.get("taken_at"),
                "source": "ScrapeCreators Instagram Reels",
                "observed_at": stamp(),
            }
            if len(rows) >= 50:
                break
        paging = page.get("paging_info") or {}
        next_cursor = paging.get("max_id")
        if (
            len(rows) >= 50
            or not paging.get("more_available")
            or not next_cursor
            or next_cursor == cursor
        ):
            break
        cursor = next_cursor
    return score_account(list(rows.values()))


def _youtube_rows(ids, creator_role, *, fresh=False):
    if not ids:
        return []
    data = _yt(
        "videos",
        fresh=fresh,
        part="snippet,statistics,contentDetails",
        id=",".join(ids[:50]),
    )
    rows = []
    for v in data.get("items", []):
        s = v["snippet"]
        url = "https://www.youtube.com/watch?v=" + v["id"]
        seconds = re.fullmatch(
            r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", v["contentDetails"]["duration"]
        )
        duration = (
            sum(int(n or 0) * k for n, k in zip(seconds.groups(), (3600, 60, 1)))
            if seconds
            else None
        )
        stats = v.get("statistics", {})
        rows.append(
            {
                "id": uid(url),
                "url": url,
                "platform": "YouTube",
                "creator": s["channelTitle"],
                "creator_role": creator_role,
                "title": s["title"],
                "caption": s["description"][:500],
                "thumbnail_url": s["thumbnails"]["medium"]["url"],
                "views": int(stats["viewCount"]) if "viewCount" in stats else None,
                "likes": int(stats["likeCount"]) if "likeCount" in stats else None,
                "comments": int(stats["commentCount"])
                if "commentCount" in stats
                else None,
                "shares": None,
                "published_at": s["publishedAt"],
                "duration": duration,
                "source": "YouTube Data API",
                "account_source": "https://www.youtube.com/channel/" + s["channelId"],
                "observed_at": stamp(),
            }
        )
    return rows


def youtube_account(handle, *, fresh=False):
    channels = _yt(
        "channels",
        part="contentDetails",
        **(
            {"id": handle}
            if re.fullmatch(r"UC[\w-]{22}", handle)
            else {"forHandle": handle}
        ),
    ).get("items", [])
    if not channels:
        return []
    pid = channels[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    uploads = _yt(
        "playlistItems",
        fresh=fresh,
        part="contentDetails",
        playlistId=pid,
        maxResults=50,
    ).get("items", [])
    return score_account(
        _youtube_rows(
            [v["contentDetails"]["videoId"] for v in uploads], "creator", fresh=fresh
        )
    )


def _peer_names(brief):
    raw = (
        brief.get("competitor_brands")
        or brief.get("competitors")
        or brief.get("competitor_set")
        or []
    )
    return [x if isinstance(x, str) else x.get("brand", "") for x in raw]


def _account_links(brand):
    """Only accept account links from known brand sites and exclude retailer/parent accounts."""
    from selectolax.lexbor import LexborHTMLParser

    from ..competitors import BRAND_DOMAINS, SIGNAL_DOMAINS, _words

    known = ACCOUNTS.get(brand.casefold())
    if known:
        return {"instagram": known, "youtube": BRAND_CHANNELS.get(brand.casefold())}
    domain = BRAND_DOMAINS.get(brand) or SIGNAL_DOMAINS.get(_words(brand))
    if not domain:
        return {}
    source = "https://" + domain + "/"
    normalized = re.sub(r"[^a-z0-9]", "", _words(brand))

    def fetch():
        with httpx.stream("GET", source, timeout=8, follow_redirects=True) as r:
            r.raise_for_status()
            chunks = []
            total = 0
            for block in r.iter_bytes():
                chunks.append(block)
                total += len(block)
                if total >= 2_500_000:
                    break
        result = {}
        for link in LexborHTMLParser(b"".join(chunks)).css("a[href]"):
            href = link.attributes.get("href", "")
            u = urlsplit(href)
            if u.scheme != "https":
                continue
            handle = u.path.strip("/")
            if (
                u.hostname in ("instagram.com", "www.instagram.com")
                and re.fullmatch(r"[\w.]{2,40}", handle)
                and normalized in re.sub(r"[^a-z0-9]", "", handle.lower())
            ):
                result["instagram"] = [handle, source]
            if (
                u.hostname in ("www.youtube.com", "youtube.com")
                and handle.startswith("@")
                and normalized in re.sub(r"[^a-z0-9]", "", handle.lower())
            ):
                result["youtube"] = handle[1:]
        return result

    try:
        return _cache("brand_social_links:" + source, fetch, ttl=86400 * 30)
    except (ValueError, httpx.HTTPError):
        return {}


def recommended_sources(rows, brief, limit=2):
    """Pick category-matching measured outliers with distinct creator identities."""
    from ..competitors import CATEGORIES

    category = brief.get("category") or brief.get("product", {}).get("category", "")
    category_key = category.casefold()
    aliases = {"eye": "eye care", "hair": "hair", "body": "body"}
    pattern = CATEGORIES.get(
        aliases.get(category_key, category_key), ("", re.escape(category))
    )[1]
    today = datetime.now(timezone.utc)

    def priority(r):
        raw = r.get("published_at")
        try:
            date = (
                datetime.fromtimestamp(raw, timezone.utc)
                if isinstance(raw, (int, float))
                else datetime.fromisoformat(raw.replace("Z", "+00:00"))
            )
            recent = (today - date).days <= 365
        except (ValueError, AttributeError, TypeError, OverflowError):
            recent = False
        return (
            not recent,
            r.get("creator_role") != "brand",
            -(r.get("outlier_ratio") or 0),
            r["url"],
        )

    seen = set()
    found = []
    for row in sorted(rows, key=priority):
        if len(found) >= limit:
            break
        if (
            row.get("evidence") != "outlier-backed"
            or not row.get("creator")
            or row["creator"] in seen
            or not row.get("duration")
            or row["duration"] > 180
            or row.get("platform") not in {"Instagram", "YouTube"}
            or not pattern
            or not re.search(
                pattern,
                (row.get("title") or "") + " " + (row.get("caption") or ""),
                re.IGNORECASE,
            )
        ):
            continue
        found.append(row)
        seen.add(row["creator"])
    return found


def discover(run_dir, brief):
    root = Path(run_dir) / "research"
    category = brief.get("category") or brief.get("product", {}).get(
        "category", "Skincare"
    )
    brands = _peer_names(brief)
    signature = uid(
        json.dumps(
            [category, sorted(brands), brief.get("creator_handles", CREATORS)],
            sort_keys=True,
        )
    )
    cached = root / "discovery.json"
    meta = root / "discovery-coverage.json"
    if (
        cached.is_file()
        and meta.is_file()
        and time.time() - cached.stat().st_mtime < 86400
        and json.loads(meta.read_text()).get("signature") == signature
    ):
        return json.loads(cached.read_text())
    candidates, coverage = {}, []

    def record(kind, name, loader):
        try:
            items = loader()
            return items, {"source": kind, "name": name, "count": len(items)}
        except (httpx.HTTPError, KeyError, TypeError, ValueError, RuntimeError) as e:
            status = (
                e.response.status_code
                if isinstance(e, httpx.HTTPStatusError)
                else type(e).__name__
            )
            return [], {"source": kind, "name": name, "count": 0, "issue": str(status)}

    identity = {b: _account_links(b) for b in brands}
    accounts = [
        (b, *links["instagram"])
        for b, links in identity.items()
        if links.get("instagram")
    ]
    jobs = [
        ("Instagram", b, lambda b=b, h=h, src=src: instagram_account(h, b, src))
        for b, h, src in accounts
    ]

    def brand_channel(brand):
        rows = youtube_account(identity[brand]["youtube"])
        for row in rows:
            row.update(brand=brand, creator_role="brand")
        return rows

    jobs += [
        ("YouTube brand", b, lambda b=b: brand_channel(b))
        for b in brands
        if identity[b].get("youtube")
    ]
    jobs += [
        ("YouTube", h, lambda h=h: youtube_account(h))
        for h in brief.get("creator_handles", CREATORS)
    ]

    def keyword():
        res = _yt(
            "search",
            part="id",
            q=f"{category} review India",
            regionCode="IN",
            type="video",
            videoDuration="short",
            maxResults=12,
        )
        rows = _youtube_rows(
            [v["id"]["videoId"] for v in res.get("items", [])], "keyword"
        )
        for row in rows:
            row.update(evidence="discovered", outlier_ratio=None)
        return rows

    jobs.append(("YouTube search", category, keyword))

    def social():
        from contextlib import closing

        from ..client import Client

        with closing(Client("data/cache", lambda *args, **kwargs: None)) as c:
            hits = c.search(
                f"{category} Indian skincare reels reviews", sources=["social"]
            )
        rows = []
        for hit in hits:
            try:
                platform, url = checked_url(hit.get("url", ""))
            except ValueError:
                continue
            rows.append(
                {
                    "id": uid(url),
                    "url": url,
                    "platform": platform,
                    "title": hit.get("title", ""),
                    "creator": None,
                    "evidence": "discovered",
                    "outlier_ratio": None,
                    "source": "Crustdata social search",
                    "observed_at": stamp(),
                }
            )
        return rows

    if os.getenv("CRUSTDATA_API_KEY"):
        jobs.append(("Crustdata social", category, social))
    with ThreadPoolExecutor(max_workers=3) as pool:
        for found, cov in pool.map(lambda j: record(*j), jobs):
            coverage.append(cov)
            for item in found:
                candidates.setdefault(item["url"], item)
    for brand in set(brands) - {b for b, _, _ in accounts}:
        coverage.append(
            {
                "source": "Instagram",
                "name": brand,
                "count": 0,
                "issue": "Verified handle unavailable",
            }
        )
    rows = sorted(
        candidates.values(), key=lambda r: (-(r.get("outlier_ratio") or 0), r["url"])
    )
    persist_thumbnails(run_dir, rows)
    dump(cached, rows)
    dump(
        meta,
        {
            "signature": signature,
            "observed_at": stamp(),
            "accounts": coverage,
            "window": "Up to 50 latest account uploads; Instagram excludes pinned and collaborator-owned posts. At least five observed view counts and nonzero median required.",
            "breakout_ratio": 3,
        },
    )
    return rows


def ad_lifetime(start_date, end_date=None, active=False):
    """Reported public ad dates show longevity. A paused ad needs an end date."""
    from datetime import date

    def parse(v):
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        if isinstance(v, (int, float)) and v > 0:
            return datetime.fromtimestamp(v, timezone.utc).date()
        if isinstance(v, str) and v:
            return date.fromisoformat(v[:10])
        return None

    start, end = parse(start_date), parse(end_date)
    today = datetime.now(timezone.utc).date()
    if end is None and active is True:
        end = today
    if start and (start > today or (end and (end < start or end > today))):
        raise ValueError(
            "Ad dates must be chronologically ordered and already observed."
        )
    days = (end - start).days if start and end else None
    return {
        "observed_days_running": days,
        "longevity_signal": days >= 30 if days is not None else None,
    }


def readback_baseline(post, brief):
    """Verify publisher identity before comparing independently observed platform counts."""
    product = brief.get("product", {})
    platform = post.get("platform")
    result = {
        "status": "unavailable",
        "reason": None,
        "account_url": None,
        "identity_source": "https://www.dotandkey.com/",
        "creator": None,
        "platform": platform,
        "views": None,
        "baseline_n": 0,
        "baseline_median": None,
        "outlier_ratio": None,
        "evidence": "unavailable",
        "observed_at": stamp(),
    }
    brand = re.sub(r"[^a-z]+", "", str(product.get("brand", "")).lower())
    if brand not in ("dotkey", "dotandkey"):
        result["reason"] = "No verified publisher mapping for the selected brand."
        return result
    try:
        resolved, url = checked_url(post.get("url"))
        if resolved != platform:
            raise ValueError("Platform and source URL differ.")
        if platform == "Instagram":
            handle = "dotandkey.skincare"
            result["account_url"] = "https://www.instagram.com/dotandkey.skincare/"
            media = _scrape("/v1/instagram/post", fresh=True, url=url)["data"][
                "xdt_shortcode_media"
            ]
            result["creator"] = (media.get("owner") or {}).get("username")
            if (result["creator"] or "").casefold() != handle:
                result["reason"] = (
                    "The post publisher differs from the verified Dot & Key account."
                )
                return result
            account = instagram_account(
                handle, "Dot & Key", result["identity_source"], fresh=True
            )
            code = url.rstrip("/").split("/")[-1]
            matches = [
                r for r in account if r["url"].rstrip("/").split("/")[-1] == code
            ]
            views = (
                matches[0].get("views")
                if matches
                else media.get("video_play_count", media.get("video_view_count"))
            )
            peers = [r for r in account if r["url"].rstrip("/").split("/")[-1] != code]
        elif platform == "YouTube":
            channel = "UCD7U0EUBYg9YlL-zVZjkjfA"
            result["account_url"] = "https://www.youtube.com/channel/" + channel
            rows = _youtube_rows(
                [parse_qs(urlsplit(url).query)["v"][0]], "brand", fresh=True
            )
            if not rows:
                result["reason"] = "YouTube returned no public post statistics."
                return result
            item = rows[0]
            result["creator"] = item["creator"]
            if item["account_source"] != result["account_url"]:
                result["reason"] = (
                    "The video publisher differs from the verified Dot & Key channel."
                )
                return result
            views = item.get("views")
            peers = [r for r in youtube_account(channel, fresh=True) if r["url"] != url]
        else:
            result["reason"] = (
                "Verified account baselines are available for Instagram and YouTube."
            )
            return result
        observed = [
            r["views"]
            for r in peers
            if type(r.get("views")) in (float, int) and r["views"] >= 0
        ]
        center = median(observed) if observed else None
        result.update(views=views, baseline_n=len(observed), baseline_median=center)
        if (
            type(views) not in (float, int)
            or views < 0
            or len(observed) < 5
            or not center
        ):
            result["reason"] = (
                "The public counter or comparable account history is insufficient."
            )
            return result
        ratio = views / center
        result.update(
            status="measured",
            outlier_ratio=round(ratio, 3),
            evidence="outlier-backed" if ratio >= 3 else "account-observation",
        )
    except (ValueError, KeyError, IndexError, TypeError, RuntimeError, httpx.HTTPError):
        result["reason"] = (
            "Publisher or current platform statistics could not be verified."
        )
    return result


def persist_thumbnails(run_dir, rows):
    """Instagram CDN signatures expire. Retain a small public-source preview for the swipe file."""
    from io import BytesIO

    from PIL import Image, ImageOps

    from .analysis import _download

    run_dir = Path(run_dir)
    base = run_dir / "research" / "thumbnails"
    base.mkdir(parents=True, exist_ok=True)

    def capture(row):
        if row.get("platform") != "Instagram" or not row.get("thumbnail_url"):
            return
        target = base / (uid(row["url"]) + ".jpg")
        try:
            if not target.is_file():
                with tempfile.TemporaryDirectory() as temp:
                    src = Path(temp) / "remote"
                    _download(row["thumbnail_url"], src)
                    with Image.open(src) as im:
                        if im.width * im.height > 28000000:
                            return
                        preview = ImageOps.exif_transpose(im).convert("RGB")
                        preview.thumbnail((240, 360))
                        output = BytesIO()
                        preview.save(output, format="JPEG", quality=75)
                    with tempfile.NamedTemporaryFile(dir=base, delete=False) as f:
                        f.write(output.getvalue())
                    os.replace(f.name, target)
            row["thumbnail"] = str(target.relative_to(run_dir))
            row.pop("thumbnail_url", None)
        except (httpx.HTTPError, OSError, ValueError):
            return

    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(capture, rows))
    return rows
