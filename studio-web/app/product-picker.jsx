"use client";
import { useState } from "react";
import { Mark } from "./market-shared";

export default function ProductPicker({ products, busy, choose }) {
  const [query, setQuery] = useState("");
  const [handle, setHandle] = useState("");
  const terms = query.trim().toLowerCase().split(/\s+/);
  const matches = products.filter((p) => {
    const text = [p.title, p.category, p.hero_ingredient, p.handle]
      .join(" ")
      .toLowerCase();
    return terms.every((term) => text.includes(term));
  });
  return (
    <form
      className="product-picker"
      onSubmit={(e) => {
        e.preventDefault();
        if (handle && !busy) choose(handle);
      }}
    >
      <label>
        Find a product
        <input
          type="search"
          value={query}
          placeholder="Search by name or category"
          onChange={(e) => {
            setQuery(e.target.value);
            setHandle("");
          }}
        />
      </label>
      <fieldset disabled={busy}>
        <legend>
          {matches.length} matching{" "}
          {matches.length === 1 ? "product" : "products"}
        </legend>
        <div className="picker-results">
          {matches.map((p) => (
            <label key={p.handle}>
              <input
                type="radio"
                name="campaign-product"
                value={p.handle}
                checked={handle === p.handle}
                onChange={() => setHandle(p.handle)}
              />
              <span>
                {p.title}
                <small>
                  {p.category}
                  {p.size ? " · " + p.size : ""}
                </small>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <button disabled={busy || !handle} className="primary mk-button mk-dark">
        {busy ? "Creating brief…" : "Create campaign brief"}{" "}
        <Mark name="arrow" size={15} />
      </button>
    </form>
  );
}
