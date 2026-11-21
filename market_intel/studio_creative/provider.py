"""Small, cached OpenRouter transports for inspectable creative runs."""

from __future__ import annotations

import base64
import json
import os
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import httpx
from dotenv import load_dotenv
from PIL import Image

from .brief import write_json


def _access():
    load_dotenv()
    return os.getenv("OPENROUTER_API_KEY")


def compose_json(system, inputs, root=None, label="copy"):
    model = os.getenv("STUDIO_COPY_MODEL", "anthropic/claude-sonnet-5.5")
    prompt = json.dumps(inputs, ensure_ascii=False)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 4500,
    }
    digest = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    root = Path(root) if root is not None else None
    file = root / "recipes" / f"{label}-{digest}.json" if root else None
    if file and file.exists():
        cached = json.loads(file.read_text())
        return cached.get("output"), cached["recipe"]
    recipe = {
        "model": model,
        "provider": "OpenRouter",
        "prompt": system,
        "input": inputs,
        "cost_usd": None,
        "path": str(file.relative_to(root)) if file else None,
    }
    if not _access():
        return None, {
            **recipe,
            "status": "unavailable",
            "reason": "OPENROUTER_API_KEY is unset",
        }
    try:
        res = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers={"Authorization": "Bearer " + _access()},
            timeout=80,
        )
        res.raise_for_status()
        data = res.json()
        value = json.loads(data["choices"][0]["message"]["content"])
        if not isinstance(value, dict):
            raise ValueError("Expected an object")
        recipe.update(
            status="generated",
            cost_usd=data.get("usage", {}).get("cost"),
            response_id=data.get("id"),
        )
        if file:
            write_json(file, {"recipe": recipe, "output": value})
        return value, recipe
    except (ValueError, IndexError, KeyError, httpx.HTTPError) as exc:
        recipe.update(status="unavailable", reason=type(exc).__name__)
        return None, recipe


def background(root, brief):
    root = Path(root)
    model = os.getenv("STUDIO_IMAGE_MODEL", "bytedance-seed/seedream-4.5")
    product = brief["product"]
    source = product["images"][0] if product["images"] else None
    prompt = (
        "Create a photorealistic editorial still-life BACKGROUND PLATE only. "
        "No packaging, containers, bottles, tubes, people, typography, logo or lettering. "
        "Use the supplied reference solely to coordinate the lighting and colour. "
        "A softly lit sculptural plinth and strong diagonal sunshine, gentle shadows, fine stone grain. "
        f"Palette {', '.join(brief['brand_kit']['colors'][:3])}, inspired by {product.get('hero_ingredient') or product['category']}. "
        "Keep the left side quiet for a typography overlay. Reserve clear space on the right for the real packshot. "
        "Broad, uncluttered horizontal composition."
    )
    key = sha256((model + prompt + str(source)).encode()).hexdigest()[:12]
    relative = f"assets/background-{key}.jpg"
    rec_file = root / "recipes" / f"background-{key}.json"
    if (root / relative).exists() and rec_file.exists():
        return relative, json.loads(rec_file.read_text())
    recipe = {
        "model": model,
        "prompt": prompt,
        "reference": source,
        "provider": "OpenRouter",
        "cost_usd": None,
    }
    if not _access():
        return None, {
            **recipe,
            "status": "unavailable",
            "reason": "OPENROUTER_API_KEY is unset",
        }
    try:
        available = httpx.get("https://openrouter.ai/api/v1/images/models", timeout=15)
        available.raise_for_status()
        if model not in {r["id"] for r in available.json()["data"]}:
            raise ValueError("Image model unavailable")
        payload = {"model": model, "prompt": prompt, "n": 1}
        if source:
            payload["input_references"] = [
                {"type": "image_url", "image_url": {"url": source}}
            ]
        res = httpx.post(
            "https://openrouter.ai/api/v1/images",
            headers={"Authorization": "Bearer " + _access()},
            json=payload,
            timeout=150,
        )
        res.raise_for_status()
        data = res.json()
        image = Image.open(
            BytesIO(base64.b64decode(data["data"][0]["b64_json"]))
        ).convert("RGB")
        image.thumbnail((1800, 1800))
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        image.save(root / relative, quality=90)
        recipe.update(
            status="generated",
            cost_usd=data.get("usage", {}).get("cost"),
            path=relative,
        )
        write_json(rec_file, recipe)
        return relative, recipe
    except (OSError, KeyError, ValueError, IndexError, httpx.HTTPError) as exc:
        return None, {**recipe, "status": "unavailable", "reason": type(exc).__name__}
