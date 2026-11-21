// Next serializes external rewrite destinations during the standalone build.
const backend = (process.env.STUDIO_BACKEND || "http://127.0.0.1:8000").replace(/\/$/, "");

export default {
  output: "standalone",
  devIndicators: false,
  experimental: { proxyClientMaxBodySize: "64mb", proxyTimeout: 180000 },
  async rewrites() {
    return [
      // Nightly maintenance stays on the private API. Only job reads cross this proxy.
      { source: "/api/jobs/:id([a-f0-9]{32})/events", destination: backend + "/api/jobs/:id/events" },
      { source: "/api/jobs/:id([a-f0-9]{32})", destination: backend + "/api/jobs/:id" },
      { source: "/api/:section(health|version|overview|products|competitors|launches|ask|refresh|category)/:path*", destination: backend + "/api/:section/:path*" },
      { source: "/studio-api/:path*", destination: backend + "/studio/:path*" },
    ];
  },
};
