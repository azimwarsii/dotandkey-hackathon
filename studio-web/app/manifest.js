export default function manifest() {
  return {
    id: "/",
    name: "Dot & Key Market Studio",
    short_name: "D&K Studio",
    description:
      "Market research, product strategy and campaign production for Dot & Key.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    theme_color: "#1A1A1A",
    background_color: "#EDEDED",
    icons: [
      { src: "/brand/app-192.png", sizes: "192x192", type: "image/png" },
      { src: "/brand/app-512.png", sizes: "512x512", type: "image/png" },
      {
        src: "/brand/app-maskable.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
