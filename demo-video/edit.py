"""Compose the final demo: time-remap clips to VO, cards, zooms, badges, audio mix."""
import json, subprocess, sys, wave, math
import numpy as np
from PIL import Image

FF = "/Users/azim/dotandkey-hackathon/.venv/lib/python3.9/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
FILM = "/Users/azim/dotandkey-hackathon/data/studio/runs/watermelon-demo/film/hero/master.mp4"
W, H, FPS, SR = 1920, 1080, 30, 48000
OUT = sys.argv[1] if len(sys.argv) > 1 else "out/market-studio-demo.mp4"

marks = json.load(open("clips/marks.json"))
words = json.load(open("vo/words.json"))
vo_len = {k: v[-1][1] for k, v in words.items()}


def vo(k, pad):
    return vo_len[k] + pad


# segs: (src_start, src_end, speed or None=auto). zoom: (src_from, cx, cy, z). badges: (png, src_from, src_to)
SC = [
    dict(k="s01_hook", card="cards/title.png", card_len=3.2, xfade=0.5, segs=[(0.8, 8.9, None)],
         target=vo("s01_hook", 0.85), vo_at=0.5),
    dict(k="s02_overview", segs=[(0.0, 20.3, None)], target=vo("s02_overview", 0.4)),
    dict(k="s03_competitors", segs=[(0.0, 11.8, None)], target=vo("s03_competitors", 0.4)),
    dict(k="s04_customers", segs=[(0.0, 11.6, None)], target=vo("s04_customers", 0.45),
         zoom=(8.5, 1500, 330, 1.55)),
    dict(k="s05_ask", segs=[(0.0, marks["s05_ask"]["enter"], None),
                           (marks["s05_ask"]["enter"], marks["s05_ask"]["answer"], 1.6),
                           (marks["s05_ask"]["answer"], 11.4, None)],
         target=vo("s05_ask", 0.45), zoom=(marks["s05_ask"]["enter"] + 0.1, 961, 538, 1.42),
         badges=[("cards/live_ask.png", marks["s05_ask"]["enter"], 99)]),
    dict(k="s06_strategy", segs=[(0.0, 20.6, None)], target=vo("s06_strategy", 0.45),
         badges=[("cards/live_brief.png", marks["s06_strategy"]["create"] - 0.2, 99)]),
    dict(k="s07_research", segs=[(0.0, 19.6, None)], target=vo("s07_research", 0.45)),
    dict(k="s08_script", segs=[(0.0, 14.9, None)], target=vo("s08_script", 0.45)),
    dict(k="s09_ads", segs=[(0.0, marks["s09_ads"]["translate_start"], None),
                           (marks["s09_ads"]["translate_start"], marks["s09_ads"]["translate_done"], 8.0),
                           (marks["s09_ads"]["translate_done"], 31.1, None)],
         target=11.0, zoom=(27.7, 960, 900, 1.45), align=("Hindi", marks["s09_ads"]["translate_start"]),
         badges=[("cards/live_hindi.png", marks["s09_ads"]["translate_start"] - 0.3, 99)]),
    dict(k="s10_video", segs=[(0.0, marks["s10_video"]["play"], None), (marks["s10_video"]["play"], 11.6, 1.0)],
         target=None, auto_target=2.8, film_at=marks["s10_video"]["play"],
         badges=[("cards/film_audio.png", marks["s10_video"]["play"] + 2.2, 99)]),
    dict(k="s11_kit", segs=[(0.0, 17.1, None)], target=8.0),
    dict(k="s12_close", card="cards/end.png", card_len=None, xfade=0.6, segs=[], target=vo("s12_close", 1.6), vo_at=0.5),
]


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def plan(sc):
    """Return (duration, out->src mapping function, src->out function) for the clip part."""
    segs = sc["segs"]
    if not segs:
        return sc["target"], None, None
    fixed = sum((e - b) / s for b, e, s in segs if s)
    auto_src = sum(e - b for b, e, s in segs if not s)
    if sc.get("target") is None:
        clip_len = fixed + sc["auto_target"]
    else:
        clip_len = sc["target"] - (sc.get("card_len") or 0)
    auto_speed = auto_src / max(clip_len - fixed, 0.1) if auto_src else 1
    table = []  # (out_start, out_end, src_start, speed)
    t = 0.0
    for b, e, s in segs:
        sp = s or auto_speed
        d = (e - b) / sp
        table.append((t, t + d, b, sp))
        t += d
    sc["speeds"] = [round(x[3], 2) for x in table]

    def o2s(o):
        for a, z, b, sp in table:
            if o < z:
                return b + (o - a) * sp
        a, z, b, sp = table[-1]
        return b + (z - a) * sp

    def s2o(s):
        for a, z, b, sp in table:
            if s <= b + (z - a) * sp:
                return a + (s - b) / sp
        return table[-1][1]
    return t, o2s, s2o


class ClipReader:
    def __init__(self, path):
        self.p = subprocess.Popen([FF, "-loglevel", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgb24",
                                   "-vf", f"fps={FPS}", "-"], stdout=subprocess.PIPE)
        self.idx = -1
        self.frame = None

    def get(self, i):
        while self.idx < i:
            buf = self.p.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                break
            self.frame = Image.frombuffer("RGB", (W, H), buf)
            self.idx += 1
        return self.frame

    def close(self):
        self.p.stdout.close()
        self.p.kill()


def zoomed(img, cx, cy, z):
    if z <= 1.001:
        return img
    cw, ch = W / z, H / z
    x0 = min(max(cx - cw / 2, 0), W - cw)
    y0 = min(max(cy - ch / 2, 0), H - ch)
    return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def load_rgba(p):
    return Image.open(p).convert("RGBA")


CH_POS = (-18, 832)  # chapter pill, bottom-left (clear of the app's floating search bar)


def main():
    enc = subprocess.Popen([FF, "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "out/video_only.mp4"], stdin=subprocess.PIPE)
    timeline = []  # (scene, start, dur)
    t_global = 0.0
    last_frame = None
    nframes = 0
    for sc in SC:
        k = sc["k"]
        clip_len, o2s, s2o = plan(sc)
        card = Image.open(sc["card"]).convert("RGB") if sc.get("card") else None
        card_len = sc.get("card_len") or (clip_len if not sc["segs"] else 0)
        if not sc["segs"]:
            clip_len = 0
        dur = card_len + clip_len
        reader = ClipReader(f"clips/{k}.mp4") if sc["segs"] else None
        chapter = load_rgba(f"cards/ch_{k}.png") if k not in ("s01_hook", "s12_close") else None
        badges = [(load_rgba(p), s2o(a), s2o(b) if b < 90 else 1e9) for p, a, b in sc.get("badges", [])]
        z = sc.get("zoom")
        z_out = s2o(z[0]) if z else None
        n = int(round(dur * FPS))
        timeline.append(dict(k=k, start=t_global, dur=n / FPS, card_len=card_len, s2o=s2o, sc=sc))
        for i in range(n):
            o = i / FPS
            xf = sc.get("xfade", 0)
            if card is not None and o < card_len:
                img = card
                if k == "s12_close" and last_frame is not None and o < xf:
                    img = Image.blend(last_frame, card, ease(o / xf))
            else:
                oc = o - card_len
                src = o2s(oc)
                img = reader.get(int(src * FPS))
                if z:
                    img = zoomed(img, z[1], z[2], 1 + (z[3] - 1) * ease((oc - z_out) / 0.6))
                if k == "s01_hook" and oc < xf:
                    img = Image.blend(card, img, ease(oc / xf))
                if chapter is not None or badges:
                    img = img.convert("RGBA")
                    if chapter is not None:
                        a = ease((oc - 0.05) / 0.35) * (1 - ease((oc - 3.6) / 0.5))
                        if a > 0:
                            layer = chapter.copy()
                            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
                            img.alpha_composite(layer, (CH_POS[0], CH_POS[1] + int((1 - a) * 16)))
                    for bimg, b0, b1 in badges:
                        if b0 <= oc < b1:
                            a = ease((oc - b0) / 0.3)
                            layer = bimg.copy()
                            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
                            img.alpha_composite(layer, (W - bimg.width + 18, CH_POS[1]))
                    img = img.convert("RGB")
            enc.stdin.write(img.tobytes())
            last_frame = img
            nframes += 1
        if reader:
            reader.close()
        print(f"{k}: {dur:5.2f}s at {t_global:6.2f}  speeds={sc.get('speeds')}")
        t_global += n / FPS
    enc.stdin.close()
    enc.wait()
    total = nframes / FPS
    print("VIDEO TOTAL", round(total, 2))

    # ---------- audio ----------
    def read_audio(path, start=None, dur=None):
        cmd = [FF, "-loglevel", "error"]
        if start is not None:
            cmd += ["-ss", str(start)]
        cmd += ["-i", path]
        if dur is not None:
            cmd += ["-t", str(dur)]
        cmd += ["-f", "f32le", "-ac", "2", "-ar", str(SR), "-"]
        raw = subprocess.run(cmd, capture_output=True, check=True).stdout
        return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()

    mix = np.zeros((int(total * SR) + SR, 2), dtype=np.float32)
    srt = []
    vo_spans = []
    for tl in timeline:
        k, sc = tl["k"], tl["sc"]
        a = read_audio(f"vo/{k}.wav")
        at = sc.get("vo_at", 0.15)
        if sc.get("align"):
            word, src_t = sc["align"]
            wt = next(w[0] for w in words[k] if w[2].lower().startswith(word.lower()))
            at = tl["card_len"] + tl["s2o"](src_t) - wt + 0.2
            at = min(max(at, 0.15), tl["dur"] - vo_len[k] - 0.1)
        start = tl["start"] + at
        i = int(start * SR)
        mix[i:i + len(a)] += a * 1.0
        vo_spans.append((start, start + len(a) / SR))
        # captions: group words into ~7-word lines
        line = []
        for w in words[k]:
            line.append(w)
            if len(line) >= 7 or w[2].endswith((".", "?", ",")) and len(line) >= 4:
                srt.append((start + line[0][0], start + line[-1][1], " ".join(x[2] for x in line)))
                line = []
        if line:
            srt.append((start + line[0][0], start + line[-1][1], " ".join(x[2] for x in line)))
        if sc.get("film_at") is not None:
            f_start = tl["start"] + tl["card_len"] + tl["s2o"](sc["film_at"])
            f_dur = tl["start"] + tl["dur"] - f_start
            fa = read_audio(FILM, 0, f_dur)
            env = np.ones(len(fa), dtype=np.float32)
            vo_end = start + len(a) / SR
            tt = f_start + np.arange(len(fa)) / SR
            duck = np.clip((tt - vo_end) / 0.4, 0, 1)  # ramp to full after VO ends
            env = 0.18 + 0.82 * duck
            fade_out = np.clip((f_start + f_dur - tt) / 0.35, 0, 1)
            fa = fa * (env * fade_out)[:, None]
            fi = int(f_start * SR)
            mix[fi:fi + len(fa)] += fa * 0.9
    mix = mix[: int(total * SR)]
    peak = np.abs(mix).max()
    if peak > 0.98:
        mix *= 0.98 / peak
    pcm = (mix * 32767).astype("<i2")
    with wave.open("out/mix.wav", "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())

    def ts(x):
        h, r = divmod(x, 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"
    with open(OUT.replace(".mp4", ".srt"), "w") as f:
        for i, (a, b, txt) in enumerate(srt, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(b + 0.15)}\n{txt}\n\n")

    subprocess.run([FF, "-loglevel", "error", "-y", "-i", "out/video_only.mp4", "-i", "out/mix.wav",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-ar", str(SR), "-shortest", "-movflags", "+faststart", OUT], check=True)
    json.dump([dict(k=t["k"], start=round(t["start"], 2), dur=round(t["dur"], 2)) for t in timeline],
              open("out/timeline.json", "w"), indent=1)
    print("WROTE", OUT)


main()
