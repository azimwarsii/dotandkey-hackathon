"""Recording helpers: CDP screencast -> frames -> CFR mp4, fake cursor, smooth moves."""
import asyncio, base64, os, subprocess, math, json, time
FF="/Users/azim/dotandkey-hackathon/.venv/lib/python3.9/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
BASE="http://127.0.0.1:3100"
HIDE_CSS = ".mk-toast,.market-coach{display:none!important} html{scroll-behavior:auto!important}"
CURSOR_JS = r"""
(() => {
  if (window.__cursorInstalled) return; window.__cursorInstalled = true;
  const install = () => {
    const c = document.createElement('div'); c.id='__cursor';
    c.innerHTML = `<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2 L4 19 L8.6 14.6 L11.6 21.4 L14.4 20.2 L11.4 13.6 L17.6 13.6 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
    Object.assign(c.style,{position:'fixed',left:'0',top:'0',zIndex:2147483647,pointerEvents:'none',transform:'translate(-200px,-200px)',filter:'drop-shadow(0 2px 3px rgba(0,0,0,.35))'});
    document.documentElement.appendChild(c);
    const st=document.createElement('style'); st.textContent=`@keyframes __rip{from{transform:translate(-50%,-50%) scale(.3);opacity:.55}to{transform:translate(-50%,-50%) scale(1);opacity:0}} .__rip{position:fixed;width:46px;height:46px;border-radius:50%;background:rgba(120,170,60,.55);pointer-events:none;z-index:2147483646;animation:__rip .5s ease-out forwards}`;
    document.documentElement.appendChild(st);
    window.addEventListener('mousemove', e => { c.style.transform=`translate(${e.clientX-4}px,${e.clientY-2}px)`; }, true);
    window.addEventListener('mousedown', e => { const r=document.createElement('div'); r.className='__rip'; r.style.left=e.clientX+'px'; r.style.top=e.clientY+'px'; document.documentElement.appendChild(r); setTimeout(()=>r.remove(),600); }, true);
  };
  if (document.documentElement) install(); else document.addEventListener('DOMContentLoaded', install);
})();
"""

class Recorder:
    def __init__(self, page, cdp, outdir):
        self.page, self.cdp, self.outdir = page, cdp, os.path.abspath(outdir)
        self.frames=None; self.mouse=(800,450)
        cdp.on("Page.screencastFrame", self._on_frame)
    def _on_frame(self, ev):
        if self.frames is not None:
            self.frames.append((time.monotonic(), ev["data"]))
        asyncio.ensure_future(self._ack(ev["sessionId"]))
    async def _ack(self, sid):
        try: await self.cdp.send("Page.screencastFrameAck", {"sessionId": sid})
        except Exception: pass
    async def start(self, name):
        self.name=name; self.frames=[]; self.t0=time.monotonic()
        await self.cdp.send("Page.startScreencast", {"format":"jpeg","quality":92,"everyNthFrame":1})
        # nudge a repaint so a first frame exists
        await self.page.mouse.move(self.mouse[0], self.mouse[1]+0.5); await self.page.mouse.move(*self.mouse)
        await asyncio.sleep(0.15)
    async def stop(self, fps=30):
        t1=time.monotonic()
        await self.cdp.send("Page.stopScreencast")
        frames=self.frames; self.frames=None
        d=os.path.join(self.outdir, self.name+"_frames"); os.makedirs(d, exist_ok=True)
        for f in os.listdir(d): os.remove(os.path.join(d,f))
        lines=["ffconcat version 1.0"]
        for i,(t,data) in enumerate(frames):
            p=os.path.join(d,f"{i:05d}.jpg"); open(p,"wb").write(base64.b64decode(data))
            nxt = frames[i+1][0] if i+1<len(frames) else t1
            lines += [f"file '{p}'", f"duration {max(nxt-t,0.001):.4f}"]
        lines.append(f"file '{os.path.join(d,f'{len(frames)-1:05d}.jpg')}'")
        open(d+".txt","w").write("\n".join(lines))
        out=os.path.join(self.outdir, self.name+".mp4")
        subprocess.run([FF,"-y","-loglevel","error","-f","concat","-safe","0","-i",d+".txt",
            "-vf",f"scale=1920:1080:flags=lanczos,fps={fps},format=yuv420p","-c:v","libx264","-preset","medium","-crf","14",out],check=True)
        print(f"  clip {self.name}: {t1-self.t0:.1f}s, {len(frames)} frames")
        return out
    # --- human-ish interaction ---
    async def move_to(self, x, y, dur=0.6):
        x0,y0=self.mouse; steps=max(int(dur*60),2)
        for i in range(1,steps+1):
            k=i/steps; e = 0.5-0.5*math.cos(math.pi*k)
            await self.page.mouse.move(x0+(x-x0)*e, y0+(y-y0)*e)
            await asyncio.sleep(dur/steps)
        self.mouse=(x,y)
    async def box(self, loc):
        await loc.scroll_into_view_if_needed()
        b=await loc.bounding_box(); return b
    async def hover(self, loc, dur=0.6, dx=0.5, dy=0.5):
        b=await self.box(loc)
        await self.move_to(b["x"]+b["width"]*dx, b["y"]+b["height"]*dy, dur)
    async def click(self, loc, dur=0.6, pause=0.25, dx=0.5, dy=0.5):
        await self.hover(loc, dur, dx, dy); await asyncio.sleep(pause)
        await self.page.mouse.down(); await asyncio.sleep(0.07); await self.page.mouse.up()
    async def scroll(self, dy, dur=1.0):
        steps=max(int(dur*60),2); done=0
        for i in range(1,steps+1):
            k=i/steps; e=0.5-0.5*math.cos(math.pi*k); target=dy*e
            await self.page.mouse.wheel(0, target-done); done=target
            await asyncio.sleep(dur/steps)
    async def scroll_to(self, y, dur=1.0):
        cur=await self.page.evaluate("window.scrollY"); await self.scroll(y-cur, dur)
    async def scroll_el(self, loc, offset=120, dur=1.0):
        y=await loc.evaluate(f"e=>e.getBoundingClientRect().top+window.scrollY-{offset}")
        await self.scroll_to(y, dur)
    async def type(self, text, delay=0.045):
        for ch in text:
            await self.page.keyboard.type(ch); await asyncio.sleep(delay)

async def setup(p, outdir):
    b = await p.chromium.launch(channel="chrome", headless=True, args=["--autoplay-policy=no-user-gesture-required","--hide-scrollbars","--window-size=1600,900"])
    ctx = await b.new_context(viewport={"width":1600,"height":900}, device_scale_factor=1)
    await ctx.add_init_script(CURSOR_JS)
    await ctx.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent=%s;document.head.appendChild(s)})" % json.dumps(HIDE_CSS))
    page = await ctx.new_page()
    cdp = await ctx.new_cdp_session(page)
    return b, page, Recorder(page, cdp, outdir)
