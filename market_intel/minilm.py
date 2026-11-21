"""Offline MiniLM sentence embeddings and an explicit, pinned weight installer."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import os
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

REPO = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
DEFAULT_DIR = Path(__file__).resolve().parents[1] / "data" / "models" / "all-MiniLM-L6-v2"
FILES = {
    "model.onnx": ("onnx/model_qint8_arm64.onnx", "4278337fd0ff3c68bfb6291042cad8ab363e1d9fbc43dcb499fe91c871902474"),
    "tokenizer.json": ("tokenizer.json", "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037"),
}


def model_dir():
    return Path(os.getenv("MARKET_INTEL_MINILM_PATH") or DEFAULT_DIR).expanduser().resolve()


def _checksum(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install():
    """Only this explicit setup path downloads public artifacts."""
    target = model_dir()
    target.mkdir(parents=True, exist_ok=True)
    for local, (remote, expected) in FILES.items():
        final = target / local
        if final.is_file() and _checksum(final) == expected:
            continue
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{remote}"
        with NamedTemporaryFile(dir=target, delete=False) as tmp:
            path = Path(tmp.name)
        try:
            with urlopen(url, timeout=90) as response, path.open("wb") as f:
                shutil.copyfileobj(response, f)
            if _checksum(path) != expected:
                raise ValueError(f"Unexpected digest for {remote} at {REVISION}")
            os.replace(path, final)
        finally:
            path.unlink(missing_ok=True)
    return target


@lru_cache(maxsize=2)
def _local_runtime(directory):
    import onnxruntime as ort
    from tokenizers import Tokenizer

    for name, (_, expected) in FILES.items():
        if _checksum(directory / name) != expected:
            raise ValueError(f"Pinned MiniLM checksum mismatch for {name}")
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    session = ort.InferenceSession(str(directory / "model.onnx"), sess_options=opts, providers=["CPUExecutionProvider"])
    tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=256)
    return session, tokenizer


def embed(clauses, directory):
    """Attention-masked mean pooling followed by L2 normalization, matching the model card."""
    import numpy as np

    session, tokenizer = _local_runtime(directory)
    blocks = []
    for offset in range(0, len(clauses), 32):
        batch = [tokenizer.encode(clause) for clause in clauses[offset:offset+32]]
        width = max(len(item.ids) for item in batch)
        inputs = {}
        for name, attr in (("input_ids", "ids"), ("attention_mask", "attention_mask"), ("token_type_ids", "type_ids")):
            array = np.zeros((len(batch), width), dtype=np.int64)
            for index, item in enumerate(batch):
                tokens = getattr(item, attr)
                array[index, :len(tokens)] = tokens
            inputs[name] = array
        hidden = session.run(["last_hidden_state"], inputs)[0]
        mask = inputs["attention_mask"][:, :, None].astype(np.float32)
        pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
        blocks.append(pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12))
    return np.concatenate(blocks)


if __name__ == "__main__":
    print(f"Installed {REPO}@{REVISION} in {install()}")
