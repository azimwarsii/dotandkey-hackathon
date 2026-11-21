"use client";
import { useEffect, useRef } from "react";

export function useExampleTyping(enabled, example, setValue) {
  const timer = useRef();
  const cancel = () => clearInterval(timer.current);
  useEffect(() => {
    if (!enabled) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setValue(example);
      return;
    }
    let length = 0;
    setValue("");
    timer.current = setInterval(() => {
      length += 1;
      setValue(example.slice(0, length));
      if (length >= example.length) cancel();
    }, 95);
    return cancel;
  }, [enabled, example, setValue]);
  return cancel;
}

const prompts = {
  product: [
    "2 · Product detail",
    "Open Reviews to read the comments behind this product.",
    "Open reviews",
  ],
  evidence: [
    "3 · Customer evidence",
    "Read a customer’s words, then follow a saved Watermelon campaign into Studio.",
    "Open example brief",
  ],
  brief: [
    "4 · Campaign brief",
    "Check the catalog claims and customer evidence. Continue to References to find a creative example.",
    "Explore references",
  ],
  references: [
    "5 · Reference library",
    "We're filtering the saved references by creator. Open a matching card to inspect its hook and timing.",
    "Open reference breakdown",
  ],
  breakdown: [
    "6 · Reference breakdown",
    "Select a timestamp to see the frame behind a finding, then open video production.",
    "Explore video production",
  ],
  video: [
    "7 · Video production",
    "Try the progress replay below. You can also play any saved film and inspect its checks.",
    "Finish walkthrough",
  ],
};

export function TourCoach({ step, advance, exit }) {
  const prompt = prompts[step];
  if (!prompt) return null;
  return (
    <aside className="tour-guide" aria-label="Guided walkthrough">
      <div>
        <small>Guided walkthrough · {prompt[0]}</small>
        <p>{prompt[1]}</p>
      </div>
      <div className="tour-controls">
        <button onClick={exit}>Exit tour</button>
        <button className="mk-button mk-dark" onClick={advance}>
          {prompt[2]} →
        </button>
      </div>
    </aside>
  );
}
