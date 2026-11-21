import "./studio.css";
import "./studio-flow.css";
import "./experience.css";
export const metadata = {
  title: "Dot & Key Market Studio",
  description: "Explore skincare markets and turn evidence into campaigns.",
  icons: { icon: "/brand/app-192.png", apple: "/brand/app-192.png" },
  appleWebApp: {
    capable: true,
    title: "Market Studio",
    statusBarStyle: "default",
  },
};
export const viewport = { themeColor: "#1A1A1A" };
export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
