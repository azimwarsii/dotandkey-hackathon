"""Extract timestamped frames, shot boundaries, OCR and audio from local media."""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
import wave
from functools import lru_cache
from pathlib import Path

import cv2
import httpx
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageOps

cv2.setNumThreads(1)
MAX_DURATION = 180


def ff(*args, timeout=150, check=True):
    executable = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
    return subprocess.run(
        [
            executable,
            "-hide_banner",
            "-nostdin",
            "-protocol_whitelist",
            "file,pipe",
            *map(str, args),
        ],
        capture_output=True,
        check=check,
        timeout=timeout,
    )


def video_info(path):
    cap = cv2.VideoCapture(str(path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not math.isfinite(fps) or not math.isfinite(frames) or not fps or frames < 1:
            raise ValueError("Media contains no readable video frames.")
        return round(frames / fps, 3), fps
    finally:
        cap.release()


def normalize_video(src, dest):
    # Reject unbounded uploads before decoding a long reference in full.
    ff(
        "-v",
        "error",
        "-y",
        "-i",
        src,
        "-t",
        MAX_DURATION + 1,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        "scale='min(512,iw)':-2,setsar=1",
        "-r",
        "24",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "25",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        dest,
    )
    duration, _ = video_info(dest)
    if duration > MAX_DURATION + 0.1:
        raise ValueError("Use an excerpt of three minutes or less.")


def shot_times(path, duration):
    detection = ff(
        "-i",
        path,
        "-an",
        "-vf",
        r"scale=160:-2,select=gt(scene\,0.30),showinfo",
        "-f",
        "null",
        "-",
        timeout=90,
    )
    entries = re.findall(rb"pts_time:\s*([\d.]+)", detection.stderr)
    cuts = [0.0]
    for entry in entries:
        when = round(float(entry), 3)
        if when - cuts[-1] >= 0.25 and duration - when >= 0.15:
            cuts.append(when)
    return cuts


@lru_cache(maxsize=1)
def _ocr():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)


@lru_cache(maxsize=1)
def _faces():
    return cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )


def _pack_reference(path):
    if not path or not Path(path).is_file():
        return None
    raw = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if raw is None:
        return None
    raw = cv2.resize(raw, (320, int(raw.shape[0] * 320 / raw.shape[1])))
    kp, desc = cv2.ORB_create(nfeatures=800).detectAndCompute(raw, None)
    return (kp, desc) if desc is not None and len(kp) >= 10 else None


def _pack_present(gray, ref):
    if ref is None:
        return None
    kp, desc = cv2.ORB_create(nfeatures=1000).detectAndCompute(gray, None)
    if desc is None or len(kp) < 10:
        return False
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(ref[1], desc, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.72 * p[1].distance]
    if len(good) < 10:
        return False
    a = np.float32([ref[0][m.queryIdx].pt for m in good])
    b = np.float32([kp[m.trainIdx].pt for m in good])
    _, mask = cv2.findHomography(a, b, cv2.RANSAC, 4)
    return bool(mask is not None and int(mask.sum()) >= 9 and mask.mean() >= 0.55)


def _frame(image, t, rel, directory, ref, hook, cut, do_ocr):
    image.thumbnail((512, 750))
    key = f"frame-{round(t * 1000):07d}.jpg"
    image.save(directory / key, quality=83)
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    faces = _faces().detectMultiScale(gray, 1.15, 5, minSize=(28, 28))
    words = []
    if do_ocr:
        result, _ = _ocr()(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        for box, word, confidence in result or []:
            if confidence >= 0.55:
                words.append(
                    {
                        "text": word,
                        "confidence": round(confidence, 2),
                        "box": [
                            [round(x / rgb.shape[1], 3), round(y / rgb.shape[0], 3)]
                            for x, y in box
                        ],
                    }
                )
    quantized = (
        image.convert("RGB")
        .resize((96, 96))
        .quantize(colors=4, method=Image.Quantize.MEDIANCUT)
    )
    palette = quantized.getpalette()
    colors = [
        "#" + bytes(palette[i * 3 : i * 3 + 3]).hex()
        for _, i in sorted(quantized.getcolors(), reverse=True)
    ]
    density = sum(abs(cv2.contourArea(np.float32(w["box"]))) for w in words)
    grid = np.array_split(gray, 3, axis=0)
    layout = [
        [round(float(cell.mean()) / 255, 2) for cell in np.array_split(row, 3, axis=1)]
        for row in grid
    ]
    return {
        "id": key[:-4],
        "time": t,
        "path": f"{rel}/{key}",
        "hook": hook,
        "cut": cut,
        "ocr": " ".join(w["text"] for w in words),
        "ocr_words": words,
        "ocr_checked": do_ocr,
        "text_density": round(min(1, density), 4) if do_ocr else None,
        "palette": colors,
        "layout_luminance": layout,
        "face_count": len(faces),
        "faces": [
            [
                round(x / rgb.shape[1], 3),
                round(y / rgb.shape[0], 3),
                round(w / rgb.shape[1], 3),
                round(h / rgb.shape[0], 3),
            ]
            for x, y, w, h in faces
        ],
        "product_match": _pack_present(gray, ref),
    }


def frame_analysis(paths, directory, rel, ref_path, duration, cuts, image_post):
    ref = _pack_reference(ref_path)
    frames = []
    if image_post:
        for i, path in enumerate(paths):
            with Image.open(path) as im:
                frames.append(
                    _frame(
                        ImageOps.exif_transpose(im).convert("RGB"),
                        float(i),
                        rel,
                        directory,
                        ref,
                        i == 0,
                        True,
                        True,
                    )
                )
    else:
        cap = cv2.VideoCapture(str(paths[0]))
        times = sorted(
            {
                *cuts,
                *[
                    v
                    for v in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
                    if v < duration - 0.05
                ],
            }
        )
        try:
            for t in times:
                cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * t)
                ok, frame = cap.read()
                if ok:
                    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    frames.append(
                        _frame(image, t, rel, directory, ref, t <= 3, t in cuts, True)
                    )
        finally:
            cap.release()
    if not frames:
        raise ValueError("No decodable images found.")
    cols = min(5, len(frames))
    w, h = 150, 175
    contact = Image.new("RGB", (cols * w, math.ceil(len(frames) / cols) * h), "#152222")
    draw = ImageDraw.Draw(contact)
    for i, item in enumerate(frames):
        x, y = i % cols * w, i // cols * h
        with Image.open(directory / Path(item["path"]).name) as f:
            f.thumbnail((w - 8, h - 23))
            contact.paste(f, (x + (w - f.width) // 2, y + 3))
        label = (
            (f"Slide {i + 1}" if image_post else f"{item['time']:.2f}s")
            + ("  HOOK" if item["hook"] else "")
            + ("  CUT" if item["cut"] and not image_post else "")
        )
        draw.text(
            (x + 5, y + h - 16), label, fill=("#B2EDAB" if item["hook"] else "white")
        )
    contact.save(directory / "contact-sheet.jpg", quality=85)
    return frames


def _segments(pcm):
    import webrtcvad

    detector = webrtcvad.Vad(2)
    step = 480
    vad = [
        detector.is_speech(pcm[i : i + step].tobytes(), 16000)
        for i in range(0, len(pcm) - step + 1, step)
    ]
    return vad, step


def _transcribe(pcm, vad, step, directory, warnings):
    key = os.getenv("SARVAM_API_KEY")
    segs = []
    source = None
    if key:
        # Sarvam REST supplies text per audio clip. Times describe the sent clip, not word-level alignment.
        for offset in range(0, len(pcm), 16000 * 10):
            chunk = pcm[offset : offset + 16000 * 10]
            if not any(vad[offset // step : (offset + len(chunk)) // step]):
                continue
            with tempfile.TemporaryFile() as f:
                with wave.open(f, "wb") as w:
                    w.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                    w.writeframes(chunk.tobytes())
                f.seek(0)
                try:
                    res = httpx.post(
                        "https://api.sarvam.ai/speech-to-text",
                        headers={"api-subscription-key": key},
                        data={"model": "saaras:v3", "mode": "transcribe"},
                        files={"file": ("audio.wav", f, "audio/wav")},
                        timeout=40,
                    )
                    res.raise_for_status()
                    out = res.json()
                except (httpx.HTTPError, ValueError):
                    warnings.append("Sarvam could not transcribe every audio interval.")
                    break
                source = "Sarvam Saaras v3, 10-second clip intervals"
                if out.get("transcript", "").strip() and not re.fullmatch(
                    r"[\[\( ]*(?:music|background music|singing|silence)[.\]\) ]*",
                    out["transcript"].strip(),
                    re.IGNORECASE,
                ):
                    segs.append(
                        {
                            "start": offset / 16000,
                            "end": round((offset + len(chunk)) / 16000, 3),
                            "text": out["transcript"].strip(),
                            "language": out.get("language_code"),
                        }
                    )
        else:
            return segs, source
    from .whisper_setup import model_path

    local_model = model_path()
    if local_model.is_dir():
        try:
            from faster_whisper import WhisperModel

            whisper = WhisperModel(
                str(local_model),
                device="cpu",
                compute_type="int8",
                local_files_only=True,
            )
            segments, _ = whisper.transcribe(
                pcm.astype(np.float32) / 32768, vad_filter=True
            )
            return [
                {
                    "start": round(x.start, 2),
                    "end": round(x.end, 2),
                    "text": x.text.strip(),
                }
                for x in segments
            ], "faster-whisper"
        except (ImportError, RuntimeError, ValueError, OSError):
            warnings.append("The configured local Whisper model was unavailable.")
    if not source:
        warnings.append(
            "Speech transcription unavailable. Configure Sarvam or STUDIO_WHISPER_MODEL."
        )
    return segs, source


def audio_analysis(path, directory, rel, warnings):
    res = ff(
        "-loglevel",
        "error",
        "-i",
        path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "s16le",
        "pipe:1",
        check=False,
    )
    pcm = np.frombuffer(res.stdout, dtype="<i2")
    if not len(pcm):
        return {"present": False}, []
    vad, step = _segments(pcm)
    points = []
    for i in range(0, len(pcm), 3200):
        block = pcm[i : i + 3200].astype(float) / 32768
        db = max(-80.0, 20 * math.log10(max(0.0001, float(np.sqrt(np.mean(block**2))))))
        voiced = vad[i // step : (i + len(block)) // step]
        points.append(
            {
                "start": round(i / 16000, 2),
                "rms_dbfs": round(db, 1),
                "speech": sum(voiced) > len(voiced) / 2,
                "silence": db < -45,
            }
        )
    waveform = Image.new("RGB", (750, 100), "#101a1b")
    draw = ImageDraw.Draw(waveform)
    for i, p in enumerate(points):
        x = i * 750 / len(points)
        height = max(1, (80 + p["rms_dbfs"]) * 0.55)
        draw.rectangle(
            (x, 50 - height, (i + 1) * 750 / len(points), 50 + height),
            fill="#98dca8" if p["speech"] else "#70828a",
        )
    waveform.save(directory / "waveform.png")
    transcript, source = (
        _transcribe(pcm, vad, step, directory, warnings) if any(vad) else ([], None)
    )
    return {
        "present": True,
        "waveform": f"{rel}/waveform.png",
        "samples": points,
        "speech_ratio": round(sum(vad) / max(1, len(vad)), 3),
        "silence_ratio": round(sum(p["silence"] for p in points) / len(points), 3),
        "music_presence": None,
        "music_method": "VAD separates speech-like activity and silence; music is assessed separately in the semantic read.",
        "transcription_source": source,
    }, transcript
