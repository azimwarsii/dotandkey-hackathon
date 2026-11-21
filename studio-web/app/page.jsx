import MarketApp from "./market-app";
import { cookies } from "next/headers";

export const dynamic = "force-dynamic";
export default async function Page({ searchParams }) {
  const raw = await searchParams;
  const params = Object.fromEntries(
    Object.entries(raw).filter(([, v]) => typeof v === "string"),
  );
  const category = params.category || "Sunscreen";
  const backend = (
    process.env.STUDIO_BACKEND || "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
  const studio =
    params.view === "studio" ||
    (params.run &&
      !["products", "competitors", "customers", "strategy"].includes(
        params.view,
      ));
  let initialData = null,
    initialRun = null;
  const date = new Date().toISOString().slice(0, 10);
  if (!params.run && (!params.view || params.view === "overview")) {
    const q = new URLSearchParams({ category });
    if (params.as_of) q.set("as_of", params.as_of);
    if (params.compare) q.set("compare", params.compare);
    try {
      const response = await fetch(backend + "/api/overview?" + q, {
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      });
      if (response.ok) initialData = await response.json();
    } catch {}
  } else if (
    studio &&
    /^[a-zA-Z0-9_-]{1,100}$/.test(params.run || "watermelon-demo")
  ) {
    try {
      const response = await fetch(
        backend + "/studio/runs/" + (params.run || "watermelon-demo"),
        { cache: "no-store", signal: AbortSignal.timeout(4000) },
      );
      if (response.ok) initialRun = await response.json();
    } catch {}
  }
  return (
    <MarketApp
      initialRoute={params}
      initialDate={initialData?.as_of || date}
      initialWelcome={!(await cookies()).has("dk-welcome")}
      initialData={initialData}
      initialRun={initialRun}
    />
  );
}
