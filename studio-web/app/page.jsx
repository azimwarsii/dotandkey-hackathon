import Studio from "./studio";

export const dynamic = "force-dynamic";
export default async function Page({ searchParams }) {
  const params = await searchParams;
  const run = /^[a-zA-Z0-9_-]{1,100}$/.test(params.run || "")
    ? params.run
    : "watermelon-demo";
  const backend = process.env.STUDIO_BACKEND || "http://127.0.0.1:8000";
  let initial = null;
  try {
    const response = await fetch(backend + "/studio/runs/" + run, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    if (response.ok) initial = await response.json();
  } catch {}
  return <Studio first={initial} initialId={run} initialView={params.view} />;
}
