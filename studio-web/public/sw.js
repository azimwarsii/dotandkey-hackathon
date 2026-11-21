// Version updates retire old shells; responses are cached only after successful reads.
const VERSION = "dk-market-4.1";
const SHELL = VERSION + "-shell",
  DATA = VERSION + "-data",
  MEDIA = VERSION + "-media";
const baseAssets = [
  "/",
  "/manifest.webmanifest",
  "/brand/logo.svg",
  "/brand/app-192.png",
  "/brand/app-512.png",
  "/brand/app-maskable.png",
];
self.addEventListener("install", (event) =>
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL);
      await cache.addAll(baseAssets);
      const html = await (await cache.match("/")).text();
      const refs = new Set(
        [...html.matchAll(/(?:href|src)="(\/_next\/static\/[^"]+)"/g)].map(
          (m) => m[1].replaceAll("&amp;", "&"),
        ),
      );
      await Promise.allSettled([...refs].map((url) => cache.add(url)));
      await self.skipWaiting();
    })(),
  ),
);
self.addEventListener("activate", (event) =>
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys())
        if (key.startsWith("dk-market-") && ![SHELL, DATA, MEDIA].includes(key))
          await caches.delete(key);
      await self.clients.claim();
    })(),
  ),
);
async function remember(cache, key, response, limit) {
  if (!response.ok || response.status !== 200 || response.type === "opaque")
    return;
  try {
    await cache.put(key, response);
    const stored = await cache.keys();
    for (const old of stored.slice(0, Math.max(0, stored.length - limit)))
      await cache.delete(old);
  } catch {
    // Browsing remains available if the device has exhausted its storage quota.
  }
}
async function jsonRequest(request, event) {
  const cache = await caches.open(DATA);
  const old = await cache.match(request);
  const fresh = fetch(request).then(async (response) => {
    if (response.ok) {
      await remember(cache, request, response.clone(), 64);
      const path = new URL(request.url).pathname;
      if (
        path === "/api/overview" ||
        /^\/studio-api\/runs\/[^/]+$/.test(path)
      ) {
        const data = await response.clone().json();
        const asOf = data.as_of || data.brief?.as_of;
        if (asOf)
          for (const c of await self.clients.matchAll())
            c.postMessage({ type: "market-snapshot", asOf });
      }
    }
    return response;
  });
  if (old) {
    event.waitUntil(fresh.catch(() => {}));
    return old;
  }
  return fresh;
}
async function mediaRequest(request, event) {
  const cache = await caches.open(MEDIA);
  const key = request.url;
  let response = await cache.match(key);
  if (!response) {
    const online = await fetch(request);
    const length = Number(online.headers.get("Content-Length") || 0);
    const range = online.headers.get("Content-Range");
    if (online.status === 206 && range) {
      const total = Number(range.split("/")[1]);
      if (total > 0 && total <= 8 * 1024 * 1024)
        event.waitUntil(
          fetch(key)
            .then((r) => remember(cache, key, r, 60))
            .catch(() => {}),
        );
    } else if (length > 0 && length <= 8 * 1024 * 1024)
      event.waitUntil(remember(cache, key, online.clone(), 60).catch(() => {}));
    return online;
  }
  const range = request.headers.get("Range");
  if (!range) return response;
  const m = /^bytes=(\d*)-(\d*)$/.exec(range),
    content = await response.arrayBuffer();
  if (!m || (!m[1] && !m[2]))
    return new Response(null, {
      status: 416,
      headers: { "Content-Range": "bytes */" + content.byteLength },
    });
  const start = m[1]
    ? Number(m[1])
    : Math.max(0, content.byteLength - Number(m[2]));
  const end =
    m[1] && m[2]
      ? Math.min(content.byteLength - 1, Number(m[2]))
      : content.byteLength - 1;
  if (start > end || start >= content.byteLength)
    return new Response(null, {
      status: 416,
      headers: { "Content-Range": "bytes */" + content.byteLength },
    });
  return new Response(content.slice(start, end + 1), {
    status: 206,
    headers: {
      "Content-Type": response.headers.get("Content-Type"),
      "Content-Range": "bytes " + start + "-" + end + "/" + content.byteLength,
      "Content-Length": String(end - start + 1),
      "Accept-Ranges": "bytes",
    },
  });
}
self.addEventListener("fetch", (event) => {
  const req = event.request,
    url = new URL(req.url);
  if (
    req.method === "GET" &&
    req.destination === "image" &&
    url.protocol === "https:" &&
    ["cdn.shopify.com", "www.dotandkey.com", "i.ytimg.com"].includes(
      url.hostname,
    )
  ) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(MEDIA);
        const hit = await cache.match(url.href);
        if (hit) return hit;
        try {
          const res = await fetch(url, { mode: "cors", credentials: "omit" });
          const bytes = Number(res.headers.get("Content-Length"));
          if (res.ok && bytes > 0 && bytes <= 3 * 1024 * 1024)
            event.waitUntil(remember(cache, url.href, res.clone(), 60));
          if (res.ok) return res;
        } catch {}
        return fetch(req);
      })(),
    );
    return;
  }
  if (
    req.method !== "GET" ||
    url.origin !== self.location.origin ||
    req.headers.has("rsc") ||
    url.searchParams.has("_rsc") ||
    url.pathname.includes("/events") ||
    url.pathname.endsWith(".zip")
  )
    return;
  if (req.mode === "navigate") {
    event.respondWith(
      (async () => {
        const cache = await caches.open(SHELL);
        try {
          const response = await fetch(req);
          if (response.ok) await remember(cache, req, response.clone(), 100);
          return response;
        } catch {
          return (
            (await cache.match(req)) ||
            (await cache.match("/")) ||
            Response.error()
          );
        }
      })(),
    );
    return;
  }
  if (
    url.pathname.includes("/assets/") ||
    ["image", "video", "audio"].includes(req.destination)
  ) {
    event.respondWith(mediaRequest(req, event));
    return;
  }
  if (/^\/(?:api|studio-api)\//.test(url.pathname)) {
    // Job snapshots must stay current online. Retain them for offline review.
    if (url.pathname === "/api/search" || url.pathname === "/studio-api/film-quote" || /^\/studio-api\/runs(?:\/[^/]+)?$/.test(url.pathname)) {
      event.respondWith(
        (async () => {
          const cache = await caches.open(DATA);
          try {
            const r = await fetch(req);
            if (r.ok) await remember(cache, req, r.clone(), 64);
            return r;
          } catch {
            return (await cache.match(req)) || Response.error();
          }
        })(),
      );
    } else event.respondWith(jsonRequest(req, event));
    return;
  }
  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/fonts/") ||
    url.pathname.startsWith("/brand/")
  ) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(SHELL);
        const hit = await cache.match(req);
        if (hit) return hit;
        const r = await fetch(req);
        if (r.ok) await cache.put(req, r.clone());
        return r;
      })(),
    );
  }
});
self.addEventListener("message", (event) => {
  if (event.data?.type !== "warm" || !Array.isArray(event.data.urls)) return;
  event.waitUntil(
    (async () => {
      for (const url of [...new Set(event.data.urls)].slice(0, 85)) {
        const parsed = new URL(url, self.location.origin);
        if (
          parsed.origin !== self.location.origin ||
          parsed.searchParams.has("_rsc") ||
          parsed.pathname.includes("/events") ||
          !/^\/(?:_next\/static\/|brand\/|fonts\/|api\/(?:overview|products|competitors|launches|insights)|studio-api\/runs(?:\/|$))/.test(
            parsed.pathname,
          )
        )
          continue;
        const isMedia = parsed.pathname.includes("/assets/");
        const cache = await caches.open(
          isMedia
            ? MEDIA
            : /^\/(?:api|studio-api)\//.test(parsed.pathname)
              ? DATA
              : SHELL,
        );
        if (await cache.match(url)) continue;
        try {
          const r = await fetch(url);
          const size = Number(r.headers.get("Content-Length") || 0);
          if (r.ok && (!isMedia || (size > 0 && size <= 8 * 1024 * 1024)))
            await remember(cache, url, r, isMedia ? 60 : 100);
        } catch {}
      }
    })(),
  );
});
