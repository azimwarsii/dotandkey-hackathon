"""Install the pinned multilingual CPU speech model once for offline fallback."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx

REVISION = "d90ca5fe260221311c53c58e660288d3deb8d356"
SOURCE = f"https://huggingface.co/Systran/faster-whisper-tiny/resolve/{REVISION}/"
# Hugging Face's regular files expose Git blob IDs, its LFS binary exposes SHA256.
ARTIFACTS = {
    "model.bin": (
        75538270,
        "dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1",
    ),
    "config.json": (2249, "3baa18e2b321a2f489614607852a729fcd516480"),
    "tokenizer.json": (2203239, "7818adb6de9fa3064d3ff81226fdd675be1f6344"),
    "vocabulary.txt": (459861, "c9074644d9d1205686f16d411564729461324b75"),
}


def model_path():
    return Path(
        os.getenv("STUDIO_WHISPER_MODEL")
        or Path(__file__).resolve().parents[2] / "data/models/faster-whisper-tiny"
    )


def digest(path, size, expected):
    algorithm = (
        hashlib.sha256()
        if len(expected) == 64
        else hashlib.sha1(f"blob {size}\0".encode())
    )
    with path.open("rb") as data:
        for block in iter(lambda: data.read(1024 * 1024), b""):
            algorithm.update(block)
    return algorithm.hexdigest()


def install():
    folder = model_path()
    folder.mkdir(parents=True, exist_ok=True)
    for name, (size, expected) in ARTIFACTS.items():
        file = folder / name
        if (
            file.is_file()
            and file.stat().st_size == size
            and digest(file, size, expected) == expected
        ):
            continue
        with NamedTemporaryFile(dir=folder, delete=False) as out:
            tmp = Path(out.name)
        try:
            with (
                httpx.stream(
                    "GET", SOURCE + name, follow_redirects=True, timeout=90
                ) as r,
                tmp.open("wb") as out,
            ):
                r.raise_for_status()
                for block in r.iter_bytes():
                    out.write(block)
            if tmp.stat().st_size != size or digest(tmp, size, expected) != expected:
                raise ValueError(f"Unexpected model artifact: {name}")
            os.replace(tmp, file)
        finally:
            tmp.unlink(missing_ok=True)
    return folder


if __name__ == "__main__":
    print(install())
