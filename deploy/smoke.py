"""Browser smoke and offline installation checks against the deployed web origin."""

import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urljoin
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

ORIGIN = os.getenv("STUDIO_TEST_ORIGIN", "http://127.0.0.1:3000").rstrip("/")
RESULTS = Path(os.getenv("STUDIO_TEST_RESULTS", "/tmp/market-studio-smoke"))


def check(context, width):
    mobile = width < 768
    page = context.new_page()
    page.set_default_timeout(60_000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(ORIGIN, wait_until="domcontentloaded")
    page.get_by_role("button", name="Skip", exact=True).click()
    expect(page.locator('[data-tour="opportunity"]')).to_be_visible()
    expect(page.locator('[data-tour="insight"]')).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
        "Overview overflows the viewport"
    )
    page.screenshot(path=RESULTS / f"overview-{width}.png")

    health = context.request.get(ORIGIN + "/api/health")
    assert health.ok and health.json()["status"] == "ok"
    private = context.request.post(ORIGIN + "/api/jobs/nightly")
    assert private.status == 404, f"Maintenance route is visible at {private.status}"

    manifest_url = page.locator('link[rel="manifest"]').get_attribute("href")
    manifest = context.request.get(urljoin(ORIGIN, manifest_url)).json()
    assert (
        manifest["display"] == "standalone"
        and manifest["name"] == "Dot & Key Market Studio"
    )
    assert {"192x192", "512x512"} <= {i["sizes"] for i in manifest["icons"]}
    assert any("maskable" in i.get("purpose", "") for i in manifest["icons"])
    for icon in manifest["icons"]:
        assert context.request.get(urljoin(ORIGIN + manifest_url, icon["src"])).ok
    page.wait_for_function("!!navigator.serviceWorker.controller")
    session = context.new_cdp_session(page)
    errors_installing = session.send("Page.getInstallabilityErrors")[
        "installabilityErrors"
    ]
    session.detach()
    assert not errors_installing, errors_installing

    page.get_by_role("button", name="Products", exact=True).click()
    expect(page.get_by_role("searchbox", name="Filter products")).to_be_visible()
    page.goto(
        ORIGIN + "/?view=studio&run=watermelon-demo&studioStep=kit",
        wait_until="domcontentloaded",
    )
    expect(page.get_by_role("heading", name="Campaign kit ready")).to_be_visible()
    download = page.get_by_role("link", name="Download kit")
    expect(download).to_be_visible()
    if not mobile:
        response = context.request.get(
            urljoin(ORIGIN, download.get_attribute("href")), timeout=120_000
        )
        assert response.ok
        with ZipFile(io.BytesIO(response.body())) as bundle:
            assert any(v.endswith(".mp4") for v in bundle.namelist())
    await_cache = """async path => {
      const hit = await caches.match(path);
      return !!hit;
    }"""
    page.wait_for_function(await_cache, arg="/studio-api/runs/watermelon-demo")
    context.set_offline(True)
    page.reload(wait_until="domcontentloaded")
    expect(
        page.get_by_role("heading", name="Campaign kit ready", exact=True)
    ).to_be_visible()
    page.screenshot(path=RESULTS / f"offline-kit-{width}.png")
    assert not errors, json.dumps(errors)


if __name__ == "__main__":
    RESULTS.mkdir(exist_ok=True, parents=True)
    with sync_playwright() as playwright:
        options = (
            {"executable_path": os.environ["STUDIO_TEST_CHROME"]}
            if os.getenv("STUDIO_TEST_CHROME")
            else {}
        )
        for width, height in [(390, 844), (1440, 900)]:
            # Chromium disables PWA installation in incognito. Use a fresh, regular profile.
            with TemporaryDirectory(prefix="studio-browser-") as profile:
                context = playwright.chromium.launch_persistent_context(
                    profile,
                    viewport={"width": width, "height": height},
                    is_mobile=width < 768,
                    has_touch=width < 768,
                    reduced_motion="reduce",
                    **options,
                )
                try:
                    check(context, width)
                finally:
                    context.close()
    print("Desktop, mobile, ZIP, installation and offline checks passed.")
