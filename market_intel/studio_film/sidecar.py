"""The pinned upstream HTTP API used by ClipForge MCP; all requests stay local."""

import os
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx


PRIVATE_SIDECARS = {"localhost", "127.0.0.1", "::1", "clipforge", "clipforge.railway.internal"}


def is_private_sidecar(url):
    parsed = urlsplit(url)
    return parsed.scheme == "http" and parsed.hostname in PRIVATE_SIDECARS


def prepare_project(client, product, brief, script):
    def post(path, body):
        response = client.post(path, json=body)
        response.raise_for_status()
        return response.json()

    try:
        project = post(
            "/api/ingest/product", {"url": product["url"], "createProject": True}
        )["projectId"]
        ingest = "product URL"
    except (httpx.HTTPError, KeyError):
        project = None
    if not project:
        project = post(
            "/api/project",
            {
                "name": script["title"],
                "productName": product["title"],
                "productCategory": brief.get("category"),
                "videoMode": "graphic_montage",
            },
        )["id"]
        ingest = "verified catalog brief and uploaded local materials"
    prefix = f"/api/project/{project}"
    # Pass one marker per shot to keep the upstream splitter's shot count stable,
    # then restore the complete approved narration on those exact shots.
    lines = [s.get("vo", "") or s.get("text", "") for s in script["shots"]]
    imported = post(
        prefix + "/import-script",
        {
            "script": "\n".join(f"Shot {i + 1}" for i in range(len(lines))),
            "title": script["title"],
        },
    )
    identifier = imported["scriptId"]
    response = client.patch(
        prefix + "/scripts",
        json={
            "scriptId": identifier,
            "shotTexts": [
                {
                    "shotId": i + 1,
                    "voiceover": line,
                    "description": script["shots"][i]["visual"],
                }
                for i, line in enumerate(lines)
            ],
        },
    )
    response.raise_for_status()
    return project, identifier, ingest


def render_sidecar(
    base, brief, script, segments, directory, *, judges=False, exports=False
):
    if not is_private_sidecar(base):
        raise ValueError(
            "Configure ClipForge on the local machine or private compose service."
        )
    result = {}
    directory.mkdir(parents=True, exist_ok=True)
    product = brief["product"]
    with httpx.Client(base_url=base, timeout=180, trust_env=False) as client:

        def api(path, body=None):
            response = (
                client.get(path) if body is None else client.post(path, json=body)
            )
            response.raise_for_status()
            return response.json()

        api("/api/health")
        project, identifier, result["ingest"] = prepare_project(
            client, product, brief, script
        )
        prefix = f"/api/project/{project}"
        result.update(project_id=project, script_id=identifier)
        if judges and os.getenv("OPENROUTER_API_KEY"):
            report = api(
                prefix + "/script-judge",
                {
                    "scriptId": identifier,
                    "llmConfig": {
                        "baseUrl": "https://openrouter.ai/api/v1",
                        "apiKey": os.environ["OPENROUTER_API_KEY"],
                        "model": os.getenv(
                            "STUDIO_JUDGE_MODEL", "google/gemini-2.5-flash-lite"
                        ),
                    },
                },
            )
            # Rewrites are proposals. The locked export keeps the reviewed text.
            result["judges"] = {
                k: report[k] for k in report if k not in {"llmConfig", "config"}
            }
        for index, path in enumerate(segments, 1):
            response = client.post(
                prefix + "/materials",
                content=path.read_bytes(),
                headers={"content-type": "video/mp4", "x-file-name": path.name},
            )
            response.raise_for_status()
            material = response.json()["materials"][0]
            api(
                prefix + "/assets",
                {
                    "shotId": index,
                    "scriptId": identifier,
                    "type": "user_upload",
                    "sourceUrl": material["url"],
                    "provider": "studio",
                },
            )
        comp = api(
            prefix + "/compose",
            {
                "scriptId": identifier,
                "aspectRatio": "9:16",
                "renderPreset": "draft",
                "aigcBadge": True,
                "aigcBadgeText": "AI-generated",
                "captionPreset": "minimal",
                "freeTts": {"enabled": False},
                "ctaText": script.get("cta", ""),
            },
        )["compositionId"]
        result["composition_id"] = comp
        timeout = time.monotonic() + 350
        while time.monotonic() < timeout:
            state = api(prefix + "/compose?compositionId=" + comp)["composition"]
            if state["status"] == "done":
                break
            if state["status"] == "failed":
                raise RuntimeError("Upstream composition failed for " + comp)
            time.sleep(2)
        else:
            raise TimeoutError("Upstream composition still in progress: " + comp)

        def download(url, filename):
            if not url.startswith("/api/"):
                raise ValueError("Unexpected ClipForge file URL")
            response = client.get(url)
            response.raise_for_status()
            (directory / filename).write_bytes(response.content)
            return filename

        result["video"] = download(state["url"], "clipforge.mp4")
        for name in ("qc", "gate"):
            result[name] = api(prefix + "/" + name, {"compositionId": comp})
        sheet = api(
            prefix + "/contact-sheet",
            {"compositionId": comp, "frames": 9, "mode": "even"},
        )
        if sheet.get("sheet"):
            result["contact_sheet"] = download(sheet["sheet"], "clipforge-contact.jpg")
        if exports:
            result["exports"] = {}
            for platform in ("reels", "shorts"):
                payload = api(
                    prefix + "/export-platform",
                    {"compositionId": comp, "platform": platform},
                )
                result["exports"][platform] = download(
                    payload["url"], platform + ".mp4"
                )
    return result


def generate_grid(run, brief, script, base, shim_url, token, *, prepared=False):
    """Generate a single provider storyboard in a separate ClipForge editing project."""
    from .compose import safe_file
    from .providers import save_json

    folder = run / "film" / "director"
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / ("prepared-grid.json" if prepared else "grid.json")
    if receipt.exists():
        previous = __import__("json").loads(receipt.read_text())
        if previous.get("image") and (run / previous["image"]).exists():
            return previous
        raise RuntimeError(
            "Storyboard submission requires reconciliation before another charge"
        )
    if not is_private_sidecar(base):
        raise ValueError("Use a local ClipForge instance")
    with httpx.Client(base_url=base, timeout=240, trust_env=False) as client:
        project, identifier, _ = prepare_project(
            client, brief["product"], brief, script
        )
        prefix = f"/api/project/{project}"
        photo = safe_file(run, brief["product"].get("cutout")) or safe_file(
            run, brief["product"]["local_images"][0]
        )
        if not photo:
            raise ValueError("A real pack photograph is required")
        material = client.post(
            prefix + "/materials",
            files={"files": (photo.name, photo.read_bytes(), "image/png")},
        )
        material.raise_for_status()
        ref = material.json()["materials"][0]["url"]
        data = {
            "project_id": project,
            "script_id": identifier,
            "model": "local verified storyboard import"
            if prepared
            else "bytedance-seed/seedream-4.5",
            "source": brief["product"]["url"],
        }
        with receipt.open("x") as stream:
            import json

            json.dump(data, stream)
        response = client.post(
            prefix + "/storyboard-grid",
            json={
                "scriptId": identifier,
                "provider": "openai",
                "model": "gpt-image-studio-board" if prepared else "gpt-image-1",
                "apiKey": token,
                "baseUrl": shim_url,
                "productImageUrl": ref,
            },
        )
        response.raise_for_status()
        response = response.json()
        grid = client.get(response["gridPath"])
        grid.raise_for_status()
        image = folder / "storyboard.png"
        image.write_bytes(grid.content)
        data.update(
            image=image.relative_to(run).as_posix(),
            cells=response.get("count"),
            status="generated",
        )
        save_json(receipt, data)
        return data


def import_verified_board(run, brief, script, base, hero):
    """Have ClipForge split actual master frames through its storyboard-grid route."""
    import json
    import tempfile

    from PIL import Image, ImageOps

    from .compose import ffmpeg
    from .providers import save_json

    folder = run / "film" / "director"
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / "prepared-grid.json"
    if receipt.is_file():
        existing = json.loads(receipt.read_text())
        if existing.get("image") and (run / existing["image"]).is_file():
            return existing
        raise RuntimeError("The ClipForge board import has an incomplete receipt.")
    # The pinned storyboard route splits a square 3 by 3 image in row-major order.
    board = Image.new("RGB", (1536, 1536), "#fff7f6")
    with tempfile.TemporaryDirectory(dir=folder) as temp:
        for index, shot in enumerate(hero["shots"][:9]):
            frame = Path(temp) / f"frame-{index}.jpg"
            ffmpeg(
                "-ss",
                shot["start"] + min(0.35, shot["duration"] / 2),
                "-i",
                run / hero["video"],
                "-frames:v",
                "1",
                frame,
            )
            with Image.open(frame) as source:
                cell = ImageOps.contain(source.convert("RGB"), (512, 512))
            board.paste(
                cell,
                (
                    512 * (index % 3) + (512 - cell.width) // 2,
                    512 * (index // 3) + (512 - cell.height) // 2,
                ),
            )
    source = folder / "board-input.png"
    board.save(source)
    with media_adapter(source) as (_, callback, token):
        info = generate_grid(run, brief, script, base, callback, token, prepared=True)
    info["master_fingerprint"] = hero["fingerprint"]
    save_json(receipt, info)
    return info


@contextmanager
def media_adapter(source=None):
    """Run the authenticated compatibility shim for the scope of a media operation."""
    import secrets
    import socket
    import subprocess
    import sys

    token = secrets.token_hex(32)
    # With a Docker sidecar explicitly select an interface reachable from the container.
    bind_host = (
        os.getenv("STUDIO_GRID_BIND_HOST", "127.0.0.1") if source else "127.0.0.1"
    )
    callback_host = os.getenv("STUDIO_GRID_CALLBACK_HOST", "127.0.0.1")
    family = socket.AF_INET6 if ":" in bind_host else socket.AF_INET
    # In IPv6-only private networks, both the callback and the readiness probe use IPv6.
    loopback = "[::1]" if family == socket.AF_INET6 else "127.0.0.1"
    if ":" in callback_host and not callback_host.startswith("["):
        callback_host = f"[{callback_host}]"
    with socket.socket(family) as listener:
        listener.bind((bind_host, 0))
        listener.listen()
        port = listener.getsockname()[1]
        service = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "market_intel.studio_film.shim:app",
                "--fd",
                str(listener.fileno()),
                "--no-access-log",
            ],
            pass_fds=(listener.fileno(),),
            env={
                **os.environ,
                "STUDIO_PREPARED_GRID": str(source) if source else "",
                "STUDIO_SHIM_TOKEN": token,
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(60):
                try:
                    probe = httpx.get(
                        f"http://{loopback}:{port}/openapi.json",
                        timeout=0.5,
                        trust_env=False,
                    )
                    if probe.is_success:
                        break
                except httpx.HTTPError:
                    pass
                if service.poll() is not None:
                    raise RuntimeError("The local film adapter could not start")
                time.sleep(0.1)
            else:
                raise RuntimeError("The local film adapter did not start in time")
            yield (
                f"http://{loopback}:{port}/v1",
                f"http://{callback_host}:{port}/v1",
                token,
            )
        finally:
            service.terminate()
            try:
                service.wait(timeout=5)
            except subprocess.TimeoutExpired:
                service.kill()
                service.wait()


def cover_and_carousel(base, run, hero, script):
    """Render a cover and portrait carousel using the same ClipForge project."""
    import json

    from .providers import save_json

    project = hero["clipforge"]["project_id"]
    receipt = run / "film" / "hero" / "social.json"
    if receipt.exists():
        existing = json.loads(receipt.read_text())
        if existing.get("project_id") == project and all(
            (run / p).is_file() for p in [existing["cover"], *existing["carousel"]]
        ):
            return existing
    if not is_private_sidecar(base):
        raise ValueError("Configure a local ClipForge project")
    with httpx.Client(base_url=base, timeout=180, trust_env=False) as client:
        prefix = f"/api/project/{project}"
        cover = client.post(
            prefix + "/cover",
            json={
                "title": script["shots"][0]["text"],
                "frameAt": 1,
                "position": "upper",
            },
        )
        cover.raise_for_status()
        carousel = client.post(
            prefix + "/carousel", json={"width": 1080, "height": 1350}
        )
        carousel.raise_for_status()

        def store(url, name):
            if not url.startswith(f"/api/files/{project}/"):
                raise ValueError("Unexpected ClipForge media path")
            resp = client.get(url)
            resp.raise_for_status()
            destination = receipt.parent / name
            destination.write_bytes(resp.content)
            return destination.relative_to(run).as_posix()

        out = {
            "project_id": project,
            "cover": store(cover.json()["cover"], "cover.png"),
            "carousel": [
                store(url, f"carousel-{i + 1:02}.png")
                for i, url in enumerate(carousel.json()["cards"])
            ],
        }
        save_json(receipt, out)
        return out
