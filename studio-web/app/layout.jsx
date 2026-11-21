import "./studio.css";
export const metadata = {
  title: "Content Studio · Dot & Key",
  description: "Research and production for Dot & Key.",
};
export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
