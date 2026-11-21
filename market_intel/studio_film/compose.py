"""Create shot animatics, fit voice to the approved rhythm, and inspect real exports."""

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .providers import sarvam_speech

WIDTH, HEIGHT = 540, 960
FPS = 24
PAPER = "#fff8f5"
INK = "#321a28"
BERRY = "#af214c"


def ffmpeg(*args):
    executable = (
        os.getenv("FFMPEG_PATH")
        or shutil.which("ffmpeg")
        or imageio_ffmpeg.get_ffmpeg_exe()
    )
    proc = subprocess.run(
        [executable, "-hide_banner", "-nostdin", "-y", *map(str, args)],
        check=False,
        capture_output=True,
        timeout=350,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode(errors="replace")[-1200:])
    return proc


def media_duration(path):
    result = ffmpeg("-i", path, "-vn", "-f", "null", "-")
    match = re.search(r"Duration: (\d+):(\d+):([\d.]+)", result.stderr.decode())
    return int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])


def safe_file(run, relative):
    if not relative:
        return None
    p = (run / relative).resolve()
    return p if p.is_relative_to(run.resolve()) and p.is_file() else None


def _font(size, bold=False):
    fonts = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for name in fonts:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _wrap(draw, text, font, width):
    lines = []
    for word in text.split():
        if not lines or draw.textlength(lines[-1] + " " + word, font=font) > width:
            lines.append(word)
        else:
            lines[-1] += " " + word
    return lines


def shot_evidence(run, brief, shot):
    """Choose only reviewed crops and record the visual substitution explicitly."""
    product = brief["product"]
    if product.get("handle") != "watermelon-cooling-spf-50-face-sunscreen":
        return (
            product.get("cutout") or product["local_images"][0],
            "Verified catalog product photograph",
            None,
        )
    action = shot.get("visual", "").lower()
    if "split-frame" in action or "dotted" in action:
        return (
            "inputs/product-05.jpg",
            "Catalog photograph of gel on the cheek alongside the finish photograph",
            "The before and finish references are separate photographs of different people. They do not document a timed blending test.",
        )
    if "cheek" in action:
        return (
            "inputs/product-10.jpg",
            "Cropped catalog portrait with fingertips against the cheek",
            "This is a catalog pose, not a measured after-application result.",
        )
    if any(
        word in action
        for word in ("texture", "dollop", "cap opens", "spreading", "macro")
    ):
        return (
            "inputs/detail-texture.jpg",
            "Macro crop of the actual formula from the product page",
            "The still shows the texture. The cap opening, dispensing and finger motion were not filmed.",
        )
    if "in-hand" in action or "held" in action or "presenter" in action:
        return (
            "inputs/detail-presenter.jpg",
            "Catalog photograph of a presenter holding the real tube",
            "The presenter appears in a sourced still.",
        )
    return (
        product.get("cutout") or product["local_images"][0],
        "Verified product packshot",
        None,
    )


def _product_detail(run, brief, shot, size):
    path, _, _ = shot_evidence(run, brief, shot)
    photo = safe_file(run, path)
    if not photo:
        return None
    with Image.open(photo) as file:
        image = file.convert("RGB")
    w, h = image.size
    if path.endswith("/product-05.jpg"):
        # Retain the cheek and topical swatch; promotional side text is outside this crop.
        first = ImageOps.fit(
            image.crop((int(0.53 * w), int(0.05 * h), w, int(0.91 * h))),
            (size[0] // 2, size[1]),
        )
        other = safe_file(run, "inputs/product-10.jpg")
        if not other:
            return ImageOps.fit(first, size)
        with Image.open(other) as finish:
            w, h = finish.size
            right = ImageOps.fit(
                finish.convert("RGB").crop(
                    (int(0.16 * w), int(0.04 * h), int(0.94 * w), int(0.71 * h))
                ),
                (size[0] - first.width, size[1]),
            )
        split = Image.new("RGB", size, PAPER)
        split.paste(first, (0, 0))
        split.paste(right, (first.width + 2, 0))
        return split
    if path.endswith("/product-10.jpg"):
        image = image.crop((int(0.15 * w), int(0.04 * h), int(0.95 * w), int(0.71 * h)))
    return ImageOps.fit(image, size)


def shot_card(
    run, brief, shot, index, format_name, target, *, clean=False, transparent=False
):
    product = brief["product"]
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0) if transparent else PAPER)
    draw = ImageDraw.Draw(image)
    photo = safe_file(run, product.get("cutout")) or safe_file(run, "inputs/cutout.png")
    photos = [safe_file(run, p) for p in product.get("local_images", [])]
    photos = [p for p in photos if p]
    if not photo and not photos:
        raise ValueError("Import a verified product photo before rendering.")
    use_presenter = (
        "talk" in format_name.lower() or "presenter" in format_name.lower()
    ) and index == 0
    if not transparent:
        # Warm background derived from the pack's pink and coral palette.
        for y in range(HEIGHT):
            f = y / HEIGHT
            draw.line(
                (0, y, WIDTH, y), fill=(255, round(248 - 42 * f), round(242 - 29 * f))
            )
        if clean and index % 2:
            draw.ellipse((-180, 220, 630, 930), fill="#e6a59b")
            draw.ellipse((200, -90, 750, 540), fill="#f9bdad")
        elif use_presenter and safe_file(run, "inputs/detail-presenter.jpg"):
            with Image.open(run / "inputs/detail-presenter.jpg") as portrait:
                face = ImageOps.fit(portrait.convert("RGB"), (WIDTH, 600))
            image.paste(face, (0, 60))
        elif (
            not clean
            and index in (1, 2, 3)
            and safe_file(run, "inputs/detail-texture.jpg")
        ):
            detail = (
                "detail-fruit.jpg"
                if index == 1 and safe_file(run, "inputs/detail-fruit.jpg")
                else "detail-texture.jpg"
            )
            with Image.open(run / "inputs" / detail) as source:
                detail_photo = ImageOps.fit(source.convert("RGB"), (WIDTH, 555))
            image.paste(detail_photo, (0, 91))
        else:
            draw.ellipse((-110, 218, 650, 902), fill="#ffe7d7")
            draw.ellipse((60, 440, 482, 740), fill="#ffc2af")
        if photo:
            with Image.open(photo) as source:
                pack = source.convert("RGBA")
            pack.thumbnail(
                (300, 425)
                if clean or (index in (0, 4) and not use_presenter)
                else (183, 280)
            )
            x, y = (
                ((WIDTH - pack.width) // 2, 175 if not clean else 250)
                if not use_presenter
                else (34, 390)
            )
            if not clean and index in (1, 2, 3):
                x, y = (WIDTH - pack.width - 25 if index % 2 else 29), 350
            image.alpha_composite(pack, (x, y))
        else:
            with Image.open(photos[0]) as source:
                image.paste(
                    ImageOps.contain(source.convert("RGB"), (430, 445)), (56, 174)
                )
    if transparent and not photo and photos:
        photo = photos[0]
    if transparent and photo:
        # Film the original pack in the foreground. The generated plate supplies
        # light and motion behind a source-verified photo of the requested action.
        detail = (
            _product_detail(run, brief, shot, (458, 510))
            if product.get("handle") == "watermelon-cooling-spf-50-face-sunscreen"
            else None
        )
        if detail:
            mask = Image.new("L", detail.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, detail.width - 1, detail.height - 1), 22, fill=255
            )
            image.paste(detail, (42, 89), mask)
        with Image.open(photo) as source:
            pack = source.convert("RGBA")
        pack.thumbnail((116, 178) if detail else (335, 475))
        image.alpha_composite(
            pack,
            (WIDTH - pack.width - 22, 619 - pack.height)
            if detail
            else ((WIDTH - pack.width) // 2, 112),
        )
    if not clean:
        # The solid text panel keeps captions legible on moving hero footage.
        draw.rounded_rectangle((19, 652, 521, 940), radius=28, fill=PAPER)
        draw.text(
            (42, 690), "DOT & KEY", font=_font(19, True), fill=BERRY, stroke_width=0
        )
        text = shot.get("text") or shot.get("on_screen_text") or shot.get("vo", "")
        for size in range(48, 16, -1):
            font = _font(size, True)
            lines = _wrap(draw, text, font, 452)
            if len(lines) * (size + 3) <= 166:
                break
        y = 732
        for line in lines:
            draw.text((42, y), line, font=font, fill=INK, stroke_width=0)
            y += size + 3
        draw.rounded_rectangle((23, 22, 168, 52), radius=15, fill=PAPER)
        draw.text((35, 29), "AI-generated", font=_font(14), fill=INK)
    if target.suffix == ".png":
        image.save(target)
    else:
        image.convert("RGB").save(target, quality=94)


def storyboard(frames, output):
    sheet = Image.new("RGB", (660, 3 * 352), PAPER)
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames[:9]):
        with Image.open(frame) as source:
            card = ImageOps.contain(source.convert("RGB"), (185, 305))
        x = (index % 3) * 220 + 16
        y = (index // 3) * 352 + 9
        sheet.paste(card, (x, y))
        draw.text((x, y + 307), f"{index + 1:02}", fill=BERRY, font=_font(16, True))
    sheet.save(output, quality=89)


def voice_audio(line, cache, lang, paid=False, *, adapter=None):
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps([line, lang, paid]).encode()).hexdigest()[:20]
    path = cache / (key + ".wav")
    label = cache / (key + ".txt")
    if path.exists() and label.exists():
        return path, label.read_text()
    if not line.strip():
        raise ValueError("A shot needs a voice line")
    with tempfile.TemporaryDirectory(dir=cache) as tmp:
        temp = Path(tmp)
        source = temp / "voice.mp3"
        if paid:
            source = temp / "sarvam.wav"
            language = (
                "hi-IN" if lang.lower().startswith(("hi", "hinglish")) else "en-IN"
            )
            if adapter:
                response = adapter.post(
                    "/audio/speech",
                    json={
                        "input": line,
                        "language": language,
                        "voice": "ritu",
                        "response_format": "wav",
                    },
                )
                response.raise_for_status()
                source.write_bytes(response.content)
            else:
                source.write_bytes(sarvam_speech(line, language))
            provider = "Sarvam Bulbul v3"
        else:
            hindi = lang.lower().startswith(("hi", "hinglish"))
            try:
                import edge_tts

                ff = "hi-IN-SwaraNeural" if hindi else "en-IN-NeerjaNeural"

                async def speak():
                    await asyncio.wait_for(
                        edge_tts.Communicate(line, ff).save(str(source)), 6
                    )

                asyncio.run(speak())
                provider = "Edge TTS / " + ff
            except Exception as exc:  # Edge also raises provider-specific WebSocket and no-audio errors.
                if shutil.which("say"):
                    source = temp / "voice.aiff"
                    v = "Lekha" if hindi else "Rishi"
                    proc = subprocess.run(
                        ["say", "-v", v, "-o", str(source), line],
                        check=False,
                        capture_output=True,
                    )
                    if (
                        proc.returncode
                        or not source.exists()
                        or source.stat().st_size < 500
                    ):
                        subprocess.run(
                            ["say", "-o", str(source), line],
                            check=True,
                            capture_output=True,
                        )
                        v = "system default"
                    provider = "macOS speech / " + v
                elif shutil.which("espeak-ng") or shutil.which("espeak"):
                    source = temp / "voice.wav"
                    subprocess.run(
                        [
                            shutil.which("espeak-ng") or shutil.which("espeak"),
                            "-v",
                            "hi" if hindi else "en",
                            "-w",
                            str(source),
                            line,
                        ],
                        check=True,
                        capture_output=True,
                    )
                    provider = "eSpeak"
                else:
                    raise RuntimeError(
                        "Draft speech unavailable. Install an Edge-compatible voice or local eSpeak."
                    ) from exc
        normalized = temp / "normalized.wav"
        ffmpeg("-i", source, "-ar", "24000", "-ac", "1", normalized)
        normalized.replace(path)
        label.write_text(provider)
    return path, provider


def segment(frame, audio, length, destination, movie=None, movie_start=0):
    duration = max(0.25, float(length))
    vo_seconds = media_duration(audio)
    tempo = max(1, vo_seconds / max(0.2, duration - 0.06))
    # An original, restrained tonal underscore supports the holds between spoken lines.
    # Each chord fades at the cut, preserving a clean start and end.
    bed = (
        "aevalsrc=0.013*(sin(2*PI*174.61*t)+0.65*sin(2*PI*220*t)+0.4*sin(2*PI*261.63*t))"
        f":s=44100:d={duration:.5f},afade=in:d=0.16,afade=out:st={max(0, duration - 0.28):.5f}:d=0.28[bed]"
    )
    audio_filter = (
        f"[1:a]atempo={tempo:.6f},apad,atrim=duration={duration:.5f},loudnorm=I=-16:TP=-1.5:LRA=7,aresample=44100[vo];"
        f"{bed};[vo][bed]amix=inputs=2:normalize=0:duration=first[a]"
    )
    if movie:
        inputs = [
            "-stream_loop",
            "-1",
            "-ss",
            round(movie_start, 3),
            "-i",
            movie,
            "-i",
            audio,
            "-i",
            frame,
        ]
        visual = f"[0:v]crop=iw*0.32:ih:0:0,scale={WIDTH}:{HEIGHT},setsar=1,gblur=sigma=8,fps={FPS}[base];[base][2:v]overlay=0:0,format=yuv420p[v]"
    else:
        inputs = ["-loop", "1", "-framerate", str(FPS), "-i", frame, "-i", audio]
        visual = (
            f"[0:v]scale=1080:1920,zoompan=z='1+min(on*0.00042,0.028)':"
            f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={WIDTH}x{HEIGHT}:fps={FPS},format=yuv420p[v]"
        )
    ffmpeg(
        *inputs,
        "-filter_complex",
        visual + ";" + audio_filter,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        f"{duration:.5f}",
        "-r",
        FPS,
        "-threads",
        "2",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "21",
        "-c:a",
        "aac",
        "-ar",
        "44100",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        destination,
    )
    return {
        "duration": duration,
        "voice_seconds": round(vo_seconds, 2),
        "voice_tempo": round(tempo, 3),
    }


def combine(segments, target):
    # All segment filenames are generated internally and live in the same directory.
    listing = target.with_suffix(".concat")
    listing.write_text("".join("file '" + f.name + "'\n" for f in segments))
    try:
        ffmpeg(
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            listing,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            target,
        )
    finally:
        listing.unlink(missing_ok=True)


def qc(video, script, output):
    result = ffmpeg(
        "-i",
        video,
        "-vf",
        "blackdetect=d=0.4:pix_th=0.1",
        "-af",
        "volumedetect",
        "-f",
        "null",
        "-",
    )
    log = result.stderr.decode()
    black = [float(x) for x in re.findall(r"black_duration:([\d.]+)", log)]
    match = re.search(r"mean_volume: ([-\d.]+) dB", log)
    loudness = float(match[1]) if match else None
    true_peak = re.search(r"max_volume: ([-\d.]+) dB", log)
    duration = media_duration(video)
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        timeline = []
        pos = 0
        for shot in script["shots"]:
            timeline.append(min(pos + min(0.35, shot["duration"] / 2), duration - 0.08))
            pos += shot["duration"]
        for i, t in enumerate(timeline[:9]):
            name = Path(tmp) / f"{i}.jpg"
            ffmpeg("-ss", max(t, 0), "-i", video, "-frames:v", "1", name)
            if name.exists():
                frames.append(name)
        storyboard(frames, output)
    checks = {
        "decoded_with_audio": loudness is not None and loudness > -48,
        "black_frames": not black,
        "usable_loudness": bool(loudness is not None and -36 <= loudness <= -8),
        "script_duration": abs(duration - sum(s["duration"] for s in script["shots"]))
        < 0.6,
        "hook_in_three_seconds": bool(script["shots"][0].get("text")),
        "cta": bool(script.get("cta") and script.get("shots")),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "duration": round(duration, 2),
        "mean_dbfs": loudness,
        "peak_dbfs": float(true_peak[1]) if true_peak else None,
        "black_intervals_seconds": black,
        "frame_times": timeline[:9],
    }


def platform_exports(video, directory):
    from market_intel.studio.runs import progress

    outputs = {}
    for label, size in [
        ("reels", "1080:1920"),
        ("shorts", "1080:1920"),
        ("meta", "1080:1350"),
    ]:
        progress(
            f"Exporting {label.title()} at {size.replace(':', ' × ')}",
            phase="exports",
            completed=len(outputs),
            total=3,
            unit="platform files ready",
        )
        target = directory / (label + ".mp4")
        if label == "shorts":
            shutil.copyfile(directory / "reels.mp4", target)
        else:
            ffmpeg(
                "-i",
                video,
                "-vf",
                f"scale={size}:force_original_aspect_ratio=decrease,pad={size}:(ow-iw)/2:(oh-ih)/2:color=0xfff8f5",
                "-threads",
                "2",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "21",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                target,
            )
        outputs[label] = target
    return outputs
