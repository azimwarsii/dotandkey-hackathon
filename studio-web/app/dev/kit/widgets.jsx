"use client";
import { useState } from "react";
import { Overview } from "../../market-charts";
import { Status, useMarketData, withQuery, Sheet } from "../../market-shared";
import "../../market.css";
export function Kit() {
  const [category, setCategory] = useState("Sunscreen"),
    [item, setItem] = useState(null),
    [version, setVersion] = useState(0);
  const { data, error } = useMarketData(
    withQuery("/api/overview", { category }),
    null,
    version,
  );
  return (
    <main className="mk-kit">
      <header>
        <span className="mk-overline">Market Studio</span>
        <h1>Chart kit</h1>
      </header>
      {data ? (
        <Overview data={data} select={setCategory} create={setItem} />
      ) : (
        <Status error={error} retry={() => setVersion((v) => v + 1)} />
      )}
      {item && (
        <Sheet title="Insight evidence" close={() => setItem(null)}>
          <p>{item.title}</p>
          <a href={item.href}>Open the source card</a>
        </Sheet>
      )}
    </main>
  );
}
