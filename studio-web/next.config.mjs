const backend = process.env.STUDIO_BACKEND || "http://127.0.0.1:8000";

export default {
  devIndicators: false,
  experimental: { proxyClientMaxBodySize: "64mb", proxyTimeout: 180000 },
  async rewrites() {
    return [
      { source: "/studio-api/:path*", destination: backend + "/studio/:path*" },
    ];
  },
};
