"""Record every demo scene against the local app (web :3100 -> API :8000)."""
import asyncio, sys, json, time
sys.path.insert(0, "tools")
from rec import *
from playwright.async_api import async_playwright

ONLY = set(sys.argv[1:])
W = asyncio.sleep
marks = {}  # per-clip event times (seconds from clip start) for the editor


def mark(r, key):
    marks.setdefault(r.name, {})[key] = round(time.monotonic() - r.t0, 3)


async def goto(pg, url, settle=1500):
    await pg.goto(BASE + url, wait_until="networkidle")
    await pg.wait_for_timeout(settle)


async def skip_welcome(pg):
    try:
        await pg.get_by_role("button", name="Skip").click(timeout=1500)
        await pg.wait_for_timeout(500)
    except Exception:
        pass


def nav(pg, name):
    return pg.locator("header nav button, nav button").filter(has_text=name).first


def step(pg, name):
    return pg.locator("nav.studio-steps button").filter(has_text=name).first


async def s01_hook(pg, r):
    # Welcome sheet of the real app, then Skip into the Lip Balm overview.
    await goto(pg, "/?view=overview&category=Lip%20Balm", 2500)
    await r.start("s01_hook")
    await W(4.5)
    await r.click(pg.get_by_role("button", name="Skip"), 1.0)
    await W(1.8)
    await r.stop()


async def s02_overview(pg, r):
    await r.start("s02_overview")
    await r.hover(pg.locator("text=Category opportunity").first, 0.8)
    await W(0.4)
    await r.move_to(150, 600, 0.8)          # over the Lip balm bar
    await W(1.4)
    await r.move_to(1300, 470, 1.0)         # Demand index +21.7%
    await W(0.6)
    await r.move_to(1400, 560, 0.8)         # forecast line
    await W(1.4)
    await r.click(pg.locator("button").filter(has_text="Lip Balm").first, 0.9)
    await W(0.9)
    await r.click(pg.locator(".mk-categories button").filter(has_text="Sunscreen"), 0.8)
    await pg.wait_for_load_state("networkidle")
    await W(1.0)
    await r.move_to(720, 470, 0.9)          # D&K review share 5.6%
    await W(1.6)
    await r.stop()


async def s03_competitors(pg, r):
    await r.start("s03_competitors")
    await r.click(nav(pg, "Competitors"), 0.7)
    await pg.wait_for_load_state("networkidle")
    await W(0.8)
    rows = pg.locator("text=Top competitors").locator("xpath=ancestor::section[1]").locator("button, a, li")
    for y in (338, 398, 458, 518, 578):
        await r.move_to(480, y, 0.32)
        await W(0.15)
    await r.move_to(1215, 430, 0.7)        # aspect radar
    await W(1.0)
    await r.scroll(520, 1.2)               # competitor launches
    await W(0.4)
    await r.move_to(370, 480, 0.6)
    await W(1.2)
    await r.stop()


async def s04_customers(pg, r):
    await r.start("s04_customers")
    await r.click(nav(pg, "Customers"), 0.7)
    await pg.wait_for_load_state("networkidle")
    await W(0.9)
    await r.move_to(300, 345, 0.6); await W(0.5)     # greasy sticky
    await r.move_to(780, 345, 0.6); await W(0.5)     # texture
    await r.move_to(1260, 345, 0.6); await W(0.4)    # white cast
    why = pg.locator("summary").filter(has_text="Why?").nth(2)
    await r.click(why, 0.5)
    await W(0.8)
    await r.scroll(260, 1.0)
    await W(2.2)
    await r.stop()


async def s05_ask(pg, r):
    await r.start("s05_ask")
    await r.click(pg.locator("text=Search or ask").first, 0.8)
    await W(0.6)
    await r.type("Who scores higher at a lower price?", 0.05)
    await W(0.4)
    await pg.keyboard.press("Enter")
    mark(r, "enter")
    await pg.locator(".mk-answer").filter(has_text="Foxtale").first.wait_for(timeout=30000)
    mark(r, "answer")
    await W(1.6)
    src = pg.locator(".mk-answer").get_by_text("Foxtale scores higher").last
    try:
        await r.hover(src, 0.8)
    except Exception:
        await r.move_to(800, 600, 0.8)
    await W(2.6)
    await pg.keyboard.press("Escape")
    await W(0.3)
    await r.stop()


async def s06_strategy(pg, r):
    await r.start("s06_strategy")
    await r.click(nav(pg, "Strategy"), 0.7)
    await pg.wait_for_load_state("networkidle")
    await W(0.8)
    await r.scroll(700, 1.1)               # SWOT: opportunities + threats
    await W(0.6)
    await r.scroll_to(0, 0.6)
    await r.click(pg.get_by_role("button", name="Gaps", exact=True), 0.6)
    await W(0.6)
    await r.hover(pg.locator("text=mist · SPF 50 · under ₹500").first, 0.7)
    await W(0.8)
    await r.click(pg.get_by_role("button", name="Recommendations", exact=True), 0.7)
    await W(1.4)
    await r.click(pg.get_by_role("button", name="Gaps", exact=True), 0.6)
    await W(0.4)
    await r.click(pg.locator(".mk-evidence-btn").nth(1), 0.7)   # mist gap -> Create content
    await W(0.9)
    prod = pg.get_by_text("Watermelon Sunscreen SPF 50+ PA++++ With New-Age UV Filters For Oily Skin")
    await prod.scroll_into_view_if_needed()
    await W(0.3)
    await r.click(prod, 0.6)
    await W(0.4)
    await r.click(pg.get_by_role("button", name="Create campaign brief"), 0.6)
    mark(r, "create")
    await pg.wait_for_url("**studioStep=overview**", timeout=30000)
    await W(2.2)
    await r.stop()


async def s07_research(pg, r):
    await goto(pg, "/?view=studio&category=Sunscreen&run=watermelon-demo&studioStep=overview", 2000)
    await pg.evaluate("window.scrollTo(0, 330)")
    await W(0.4)
    await r.start("s07_research")
    await W(1.6)
    await r.scroll(480, 1.0)               # what we can say / what customers say
    await W(0.8)
    await r.scroll_to(0, 0.6)
    await r.click(step(pg, "References"), 0.7)
    await pg.wait_for_load_state("networkidle")
    await W(0.3)
    card = pg.locator("text=168.6× baseline").first
    await r.scroll_el(card, 330, 1.0)
    await r.hover(card, 0.6)
    await W(1.2)
    await r.scroll_to(0, 0.5)
    await r.click(step(pg, "Breakdown"), 0.7)
    await pg.wait_for_load_state("networkidle")
    await W(0.3)
    await r.scroll_el(pg.locator("text=Reference at a glance").first, 90, 1.1)
    await r.move_to(160, 520, 0.5)
    for x in (160, 300, 440, 580, 720, 860):
        await r.move_to(x, 560, 0.18)
    await W(1.0)
    await r.stop()


async def s08_script(pg, r):
    await pg.evaluate("window.scrollTo(0,0)")
    await r.start("s08_script")
    await r.click(step(pg, "Patterns"), 0.6)
    await W(1.2)
    await r.click(step(pg, "Concepts"), 0.6)
    await W(0.3)
    await r.scroll_el(pg.locator("text=Texture on Fingertips").first, 260, 0.8)
    await W(1.0)
    await r.scroll_to(0, 0.5)
    await r.click(step(pg, "Script & ads"), 0.6)
    await W(0.4)
    await r.scroll_el(pg.locator("text=Label Read").first, 60, 0.9)
    await r.move_to(1400, 470, 0.6)        # provenance "Evidence" links
    await W(0.7)
    await r.scroll_el(pg.locator("text=Storyboard grid").first, 40, 0.9)
    await W(1.0)
    await r.stop()


async def s09_ads(pg, r):
    await goto(pg, "/?view=studio&category=Sunscreen&run=watermelon-demo&studioStep=script", 1500)
    await skip_welcome(pg)
    await r.start("s09_ads")
    await r.click(pg.get_by_role("button", name="Ads", exact=True), 0.6)
    await W(0.4)
    await r.scroll_el(pg.locator("text=Static ads").first, 60, 0.8)
    await r.scroll(560, 1.0)
    await W(0.3)
    await r.scroll_to(0, 0.5)
    await r.click(pg.get_by_role("button", name="A+ content", exact=True), 0.6)
    await W(0.3)
    await r.scroll_el(pg.locator("h2, h3").filter(has_text="A+ content").last, 60, 0.8)
    await W(0.8)
    await r.scroll_to(0, 0.5)
    await r.click(pg.get_by_role("button", name="Listing", exact=True), 0.6)
    await W(0.3)
    await r.scroll_el(pg.locator("text=Translation review").first, 60, 1.0)
    await W(0.3)
    btn = pg.get_by_role("button", name="Generate translation")
    await r.click(btn, 0.6)
    mark(r, "translate_start")
    for _ in range(90):
        await W(0.5)
        txt = await pg.evaluate("document.querySelector('main')?.innerText||''")
        if "तरबूज" in txt:
            break
    mark(r, "translate_done")
    await W(0.4)
    await r.scroll(240, 0.8)
    await r.move_to(1000, 560, 0.6)
    await W(1.8)
    await r.stop()


async def s10_video(pg, r):
    await pg.evaluate("window.scrollTo(0,0)")
    await W(0.3)
    await r.start("s10_video")
    await r.click(step(pg, "Video"), 0.6)
    await pg.wait_for_load_state("networkidle")
    v = pg.locator("video").first
    await r.scroll_el(pg.locator("text=Screening room").first, 20, 1.0)
    await W(0.2)
    await r.click(v, 0.6, dy=0.45)
    await v.evaluate("v=>{v.muted=true; v.currentTime=0; return v.play()}")
    mark(r, "play")
    await W(7.0)
    await r.stop()


async def s11_kit(pg, r):
    await r.start("s11_kit")
    await r.scroll_el(pg.locator("text=Rendered pre-flight").first, 140, 1.2)
    await r.hover(pg.locator("text=passed claim guard").first, 0.7)
    await W(1.4)
    await r.scroll_to(0, 0.6)
    await r.click(step(pg, "Review"), 0.6)
    await W(0.4)
    await r.scroll_el(pg.locator("text=Variant matrix").first, 260, 0.8)
    await W(0.9)
    await r.scroll_to(0, 0.5)
    await r.click(step(pg, "Kit"), 0.6)
    await W(0.3)
    await r.scroll_el(pg.locator("text=Campaign kit ready").first, 230, 0.8)
    await W(0.6)
    await r.hover(pg.get_by_role("link", name="Download kit"), 0.7)
    await W(1.6)
    await r.stop()


SCENES = [s01_hook, s02_overview, s03_competitors, s04_customers, s05_ask, s06_strategy,
          s07_research, s08_script, s09_ads, s10_video, s11_kit]


async def main():
    async with async_playwright() as p:
        b, pg, r = await setup(p, "clips")
        # warm every route so dev-server compiles never land on camera
        for u in ["/?view=overview&category=Sunscreen", "/?view=competitors&category=Sunscreen",
                  "/?view=studio&category=Sunscreen&run=watermelon-demo&studioStep=video"]:
            await goto(pg, u, 800)
        await pg.context.clear_cookies()
        await pg.evaluate("try{localStorage.clear();sessionStorage.clear()}catch(e){}")
        for fn in SCENES:
            if ONLY and fn.__name__ not in ONLY:
                continue
            print(fn.__name__)
            try:
                await fn(pg, r)
            except Exception as e:
                print("  FAILED", fn.__name__, repr(e)[:300])
                if r.frames is not None:
                    await r.stop()
                await pg.screenshot(path=f"shots/fail_{fn.__name__}.png")
        await b.close()
    old = {}
    try:
        old = json.load(open("clips/marks.json"))
    except Exception:
        pass
    old.update(marks)
    json.dump(old, open("clips/marks.json", "w"), indent=1)


asyncio.run(main())
