"""Local OpenAI-compatible adapters for the unmodified ClipForge sidecar."""

import base64
import hmac
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from .providers import VEO, model_job_id, request, sarvam_speech

load_dotenv()


def authorize(authorization: str = Header(default="")):
    token = os.environ.get("STUDIO_SHIM_TOKEN")
    if not token or not hmac.compare_digest("Bearer " + token, authorization):
        raise HTTPException(401, "A local ClipForge shim token is required")


app = FastAPI(title="ClipForge India media adapters", dependencies=[Depends(authorize)])


@app.exception_handler(httpx.HTTPStatusError)
async def upstream_error(req, err):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        {"detail": f"Provider returned HTTP {err.response.status_code}"},
        status_code=502,
    )


async def parameters(req):
    if req.headers.get("content-type", "").startswith("application/json"):
        return await req.json()
    fields = {}
    async with req.form() as form:
        for key, value in form.multi_items():
            if isinstance(value, UploadFile):
                body = await value.read(16 * 1024 * 1024 + 1)
                if len(body) > 16 * 1024 * 1024 or value.content_type not in {
                    "image/jpeg",
                    "image/png",
                    "image/webp",
                }:
                    raise HTTPException(
                        422, "Expected a JPEG, PNG or WebP reference up to 16 MB"
                    )
                value = (
                    "data:"
                    + value.content_type
                    + ";base64,"
                    + base64.b64encode(body).decode()
                )
            if key in {"image", "image[]"}:
                fields.setdefault("_references", []).append(value)
            else:
                fields[key] = value
    return fields


@app.post("/v1/audio/speech")
def speech(data: dict):
    text = data.get("input")
    if not isinstance(text, str) or not 1 <= len(text) <= 2500:
        raise HTTPException(422, "Voice line must be 1–2500 characters")
    lang = data.get("language") or (
        "hi-IN" if any("\u0900" <= c <= "\u097f" for c in text) else "en-IN"
    )
    voice = data.get("voice", "ritu")
    if voice in {"alloy", "shimmer", "nova"}:
        voice = "ritu"
    codec = data.get("response_format", "mp3")
    if codec not in {"wav", "mp3"}:
        raise HTTPException(422, "Use wav or mp3 for speech")
    return Response(
        sarvam_speech(text, lang, voice, codec),
        media_type="audio/wav" if codec == "wav" else "audio/mpeg",
    )


@app.post("/v1/images/edits")
@app.post("/v1/images/generations")
async def images(req: Request):
    data = await parameters(req)
    if data.get("model") == "gpt-image-studio-board":
        board = os.getenv("STUDIO_PREPARED_GRID")
        if not board or not Path(board).is_file():
            raise HTTPException(
                409, "Configure a prepared storyboard for the local import."
            )
        return {
            "data": [{"b64_json": base64.b64encode(Path(board).read_bytes()).decode()}]
        }
    payload = {
        "prompt": data["prompt"],
        "model": os.getenv("STUDIO_IMAGE_MODEL", "bytedance-seed/seedream-4.5"),
    }
    if data.get("size") and data["size"] != "auto":
        sizes = str(data["size"]).split("x")
        if len(sizes) == 2 and all(x.isdigit() for x in sizes):
            w, h = map(int, sizes)
            payload["resolution"] = "2K"
            payload["aspect_ratio"] = "1:1" if w == h else ("2:3" if h > w else "3:2")
        else:
            payload["size"] = data["size"]
    refs = data.get("_references") or [data.get("image") or data.get("image[]")]
    if any(refs):
        payload["input_references"] = [
            {"type": "image_url", "image_url": {"url": ref}} for ref in refs if ref
        ]
    result = await run_in_threadpool(
        request, "openrouter", "POST", "/images", json=payload
    )
    return {
        "data": [
            {k: row[k] for k in ("b64_json", "url") if row.get(k)}
            for row in result.json()["data"]
        ]
    }


@app.post("/v1/videos")
async def submit_video(req: Request):
    data = await parameters(req)
    size = data.get("size", "720x1280")
    if size not in ("720x1280", "1280x720"):
        raise HTTPException(422, "The configured hero model uses 720p")
    seconds = int(data.get("seconds", 8))
    if seconds not in (4, 6, 8):
        raise HTTPException(422, "Use 4, 6 or 8 seconds")
    payload = {
        "model": VEO,
        "prompt": data["prompt"],
        "duration": seconds,
        "resolution": "720p",
        "generate_audio": False,
        "aspect_ratio": "9:16" if size.startswith("720x") else "16:9",
    }
    if data.get("input_reference"):
        payload["frame_images"] = [
            {
                "type": "image_url",
                "frame_type": "first_frame",
                "image_url": {"url": data["input_reference"]},
            }
        ]
    result = await run_in_threadpool(
        request, "openrouter", "POST", "/videos", json=payload
    )
    return {"id": result.json()["id"], "status": "queued"}


@app.get("/v1/videos/{job_id}")
def video_status(job_id: str):
    data = request("openrouter", "GET", "/videos/" + model_job_id(job_id)).json()
    return {
        "id": job_id,
        "status": {"pending": "queued", "processing": "in_progress"}.get(
            data["status"], data["status"]
        ),
        "progress": data.get("progress"),
        "model": data.get("model"),
        "error": data.get("error"),
    }


@app.get("/v1/videos/{job_id}/content")
def video_content(job_id: str):
    result = request(
        "openrouter",
        "GET",
        "/videos/" + model_job_id(job_id) + "/content",
        params={"index": 0},
    )
    return Response(result.content, media_type="video/mp4")
