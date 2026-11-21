"""Provider calls shared by the local filmmaker and ClipForge adapter."""

import base64
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from uuid import uuid4

import httpx

OPENROUTER = "https://openrouter.ai/api/v1"
VEO = "google/veo-3.1-lite"


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    temporary.replace(path)


def request(provider, method, path, **options):
    if provider == "openrouter":
        url = OPENROUTER + path
        headers = {"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]}
    else:
        url = "https://api.sarvam.ai" + path
        headers = {"api-subscription-key": os.environ["SARVAM_API_KEY"]}
    response = httpx.request(method, url, headers=headers, timeout=150, **options)
    response.raise_for_status()
    return response


def sarvam_speech(text, language="en-IN", voice="ritu", codec="wav"):
    data = request(
        "sarvam",
        "POST",
        "/text-to-speech",
        json={
            "text": text,
            "language_code": language,
            "speaker": voice,
            "model": "bulbul:v3",
            "output_audio_codec": codec,
            "speech_sample_rate": 24000,
        },
    ).json()
    return base64.b64decode(data["audios"][0], validate=True)


def estimate_hero():
    """Quote the two planned shots using the current public provider rate."""
    response = httpx.get(OPENROUTER + "/videos/models", timeout=20)
    response.raise_for_status()
    model = next(r for r in response.json()["data"] if r["id"] == VEO)
    rate = float(model["pricing_skus"]["duration_seconds_without_audio_720p"])
    return {
        "model": VEO,
        "resolution": "720p",
        "audio": False,
        "shot_seconds": [8, 8],
        "usd_per_second": rate,
        "estimated_usd": round(rate * 16, 6),
        "price_source": OPENROUTER + "/videos/models",
        "voice_provider": "Sarvam Bulbul v3",
    }


def model_job_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9._:-]{1,190}", value):
        raise ValueError("Invalid video job identifier")
    return value


def create_hero_clips(folder, frames, prompts, max_cost_usd, *, adapter=None):
    """Reserve each request on disk before submission; resuming only polls known job IDs."""
    quote = estimate_hero()
    if (
        max_cost_usd is None
        or not math.isfinite(float(max_cost_usd))
        or quote["estimated_usd"] > float(max_cost_usd)
    ):
        raise ValueError(
            f"The current hero estimate is USD {quote['estimated_usd']:.2f}, above the approved amount."
        )
    folder.mkdir(parents=True, exist_ok=True)
    outputs = []
    for i, (frame, prompt) in enumerate(zip(frames, prompts)):
        field = {
            "type": "image_url",
            "frame_type": "first_frame",
            "image_url": {
                "url": "data:image/jpeg;base64,"
                + base64.b64encode(frame.read_bytes()).decode()
            },
        }
        payload = {
            "model": VEO,
            "prompt": prompt,
            "duration": 8,
            "resolution": "720p",
            "aspect_ratio": "9:16",
            "generate_audio": False,
            "frame_images": [field],
        }
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        record = folder / f"job-{i + 1}.json"
        destination = folder / f"motion-{i + 1}.mp4"
        if record.exists():
            job = json.loads(record.read_text())
            if job["fingerprint"] != fingerprint:
                raise ValueError(
                    "The hero input has changed. Generate it in a new run."
                )
            if not job.get("id"):
                raise RuntimeError(
                    "Hero submission status requires reconciliation before another charge."
                )
        else:
            job = {
                "fingerprint": fingerprint,
                "prompt": prompt,
                "input_frame": frame.name,
                "quote": quote,
            }
            with record.open("x") as stream:
                json.dump(job, stream)
            if adapter:
                response = adapter.post(
                    "/videos",
                    json={
                        "prompt": prompt,
                        "size": "720x1280",
                        "seconds": 8,
                        "input_reference": field["image_url"]["url"],
                    },
                )
                response.raise_for_status()
            else:
                response = request("openrouter", "POST", "/videos", json=payload)
            data = response.json()
            job["id"] = model_job_id(data["id"])
            save_json(record, job)
        if not destination.exists():
            deadline = time.monotonic() + 900
            while time.monotonic() < deadline:
                path = "/videos/" + job["id"]
                if adapter:
                    response = adapter.get(path)
                    response.raise_for_status()
                else:
                    response = request("openrouter", "GET", path)
                data = response.json()
                job["status"] = data.get("status")
                save_json(record, job)
                if job["status"] == "completed":
                    if adapter:
                        result = adapter.get(path + "/content")
                        result.raise_for_status()
                    else:
                        result = request(
                            "openrouter",
                            "GET",
                            "/videos/" + job["id"] + "/content",
                            params={"index": 0},
                        )
                    temp = destination.with_suffix(".part")
                    temp.write_bytes(result.content)
                    temp.replace(destination)
                    break
                if job["status"] in {"failed", "cancelled", "canceled"}:
                    raise RuntimeError("Hero provider reported " + job["status"])
                time.sleep(5)
            else:
                raise TimeoutError(
                    "Video is still processing. Resume this run to poll the saved job."
                )
        outputs.append(destination)
    return quote, outputs
