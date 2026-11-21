"use client";
import { useEffect, useRef, useState } from "react";

const prefix = "dk-market:";
const read = (key) => {
  try {
    return localStorage.getItem(prefix + key);
  } catch {
    return null;
  }
};
const save = (key, value) => {
  try {
    localStorage.setItem(prefix + key, value);
  } catch {}
};
const intro = [
  [
    "Research the market",
    "Compare Dot & Key with the leading brands across ten skincare categories.",
  ],
  [
    "Follow the evidence",
    "Trace ratings, complaints and demand forecasts to their source cards.",
  ],
  [
    "Create a campaign",
    "Carry a market insight into the Studio to make and test a campaign kit.",
  ],
];
const tour = [
  [
    "overview",
    "category",
    "Choose a category",
    "Switch the market to compare a different product category.",
  ],
  [
    "overview",
    "opportunity",
    "Compare opportunities",
    "Select a bar to see the category’s measured opportunity.",
  ],
  [
    "overview",
    "ask",
    "Ask the market",
    "Find a product, a campaign or an answer backed by market evidence.",
  ],
  [
    "overview",
    "insight",
    "Follow an insight",
    "Each insight can start a campaign with the source attached.",
  ],
  [
    "products",
    "products",
    "Explore products",
    "Open a product to compare marketplace prices, ratings and reviews.",
  ],
  [
    "strategy",
    "strategy",
    "Read the strategy",
    "Trace a gap or recommendation back to evidence.",
  ],
  [
    "studio",
    "stepper",
    "Explore the Studio",
    "Follow the six steps from research through production and testing.",
  ],
];
const coaches = {
  studio: "Paste a reel on the Research step, or open a saved reference.",
  products: "Choose a product to compare its marketplace listings.",
  strategy: "Open an evidence card to see the sources behind a recommendation.",
};
function visibleTarget(name) {
  return [
    ...document.querySelectorAll(
      '[data-tour="' + name + '"], [data-tour-mobile="' + name + '"]',
    ),
  ].find(
    (el) =>
      el.getClientRects().length &&
      getComputedStyle(el).visibility !== "hidden",
  );
}
export default function AppExperience({
  navigate,
  view,
  asOf: reportDate,
  welcomeInitially,
}) {
  const [welcome, setWelcome] = useState(!!welcomeInitially),
    [page, setPage] = useState(0),
    [step, setStep] = useState(null);
  const [offline, setOffline] = useState(false),
    [asOf, setAsOf] = useState(""),
    [install, setInstall] = useState(false),
    [ios, setIos] = useState(false),
    [hint, setHint] = useState(false),
    [coach, setCoach] = useState("");
  const [toast, setToast] = useState("");
  const navigation = useRef(navigate),
    swipe = useRef(0),
    prompt = useRef(null),
    modal = useRef(null);
  navigation.current = navigate;
  useEffect(() => {
    if (reportDate && navigator.onLine) {
      setAsOf(reportDate);
      save("snapshot", reportDate);
    }
  }, [reportDate]);
  useEffect(() => {
    const visits = Number(read("visits") || 0) + 1;
    save("visits", String(visits));
    if (read("welcome")) setWelcome(false);
    setAsOf(read("snapshot") || "");
    setOffline(!navigator.onLine);
    const standalone =
      matchMedia("(display-mode: standalone)").matches || navigator.standalone;
    const apple =
      /iP(ad|hone|od)/.test(navigator.userAgent) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    setIos(apple);
    if (visits >= 2 && apple && !standalone) setInstall(true);
    const handleInstall = (e) => {
      e.preventDefault();
      prompt.current = e;
      if (visits >= 2 && !standalone) setInstall(true);
    };
    const installed = () => {
      setInstall(false);
      setHint(false);
      prompt.current = null;
    };
    const network = () => setOffline(!navigator.onLine);
    const replay = () => {
      setWelcome(true);
      setPage(0);
      setCoach("");
      setStep(null);
    };
    const message = (e) => {
      if (e.data?.type === "market-snapshot" && e.data.asOf) {
        save("snapshot", e.data.asOf);
        setAsOf(e.data.asOf);
      }
    };
    const offlineAction = () =>
      setToast(
        "Reconnect to start this action. Saved results are available offline.",
      );
    const events = [
      ["beforeinstallprompt", handleInstall],
      ["appinstalled", installed],
      ["online", network],
      ["offline", network],
      ["market:tour", replay],
      ["market:offline", offlineAction],
    ];
    events.forEach(([key, fn]) => window.addEventListener(key, fn));
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .then(async (reg) => {
          await navigator.serviceWorker.ready;
          // The install finishes after initial resources may already have loaded.
          const urls = performance
            .getEntriesByType("resource")
            .map((e) => e.name)
            .filter(
              (url) =>
                url.startsWith(location.origin + "/") &&
                /\/_next\/static\/|\/(?:studio-api|api)\/|\/fonts\/|\/brand\//.test(
                  url,
                ) &&
                !url.includes("/events"),
            );
          reg.active?.postMessage({ type: "warm", urls: urls.slice(-85) });
        })
        .catch(() => {});
      navigator.serviceWorker.addEventListener("message", message);
    }
    return () => {
      events.forEach(([key, fn]) => window.removeEventListener(key, fn));
      navigator.serviceWorker?.removeEventListener("message", message);
    };
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 5000);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (welcome && modal.current && !modal.current.matches(":modal")) {
      // The first-run sheet is already visible in the HTML before hydration.
      modal.current.close();
      modal.current.showModal();
    }
  }, [welcome]);
  useEffect(() => {
    if (
      welcome ||
      step !== null ||
      !read("welcome") ||
      !coaches[view] ||
      read("coach-" + view)
    ) {
      setCoach("");
      return;
    }
    setCoach(view);
    save("coach-" + view, "1");
  }, [view, welcome, step]);
  useEffect(() => {
    if (step === null) return;
    let cancelled = false,
      timer,
      active;
    const [screen, target, title, description] = tour[step];
    navigation.current(
      screen,
      screen === "studio"
        ? { run: "watermelon-demo", studioStep: "swipe" }
        : {},
    );
    const next = () => {
      if (step === tour.length - 1) {
        save("tour", "done");
        setStep(null);
      } else setStep(step + 1);
    };
    const show = async (tries) => {
      if (cancelled) return;
      const element = visibleTarget(target);
      if (!element && tries < 60) {
        timer = setTimeout(() => show(tries + 1), 75);
        return;
      }
      const { driver } = await import("./tour-driver");
      if (cancelled) return;
      active = driver({
        animate: !matchMedia("(prefers-reduced-motion: reduce)").matches,
        stageRadius: 16,
        stagePadding: 6,
        overlayOpacity: 0.48,
        allowClose: true,
        showButtons: ["previous", "next", "close"],
        onDestroyed: () => {
          if (!cancelled) setStep(null);
        },
        onNextClick: next,
        onPrevClick: () => setStep(Math.max(0, step - 1)),
        onCloseClick: () => setStep(null),
        onPopoverRender: ({ wrapper, footer }) => {
          const dots = document.createElement("div");
          dots.className = "tour-dots";
          dots.setAttribute("aria-label", "Step " + (step + 1) + " of 7");
          tour.forEach((_, i) => {
            let dot = document.createElement("i");
            if (i <= step) dot.className = "on";
            dots.append(dot);
          });
          wrapper.insertBefore(dots, footer);
        },
      });
      active.setSteps([
        {
          element,
          popover: {
            title,
            description,
            side: "bottom",
            align: "start",
            nextBtnText: step === 6 ? "Finish" : "Try it →",
            doneBtnText: step === 6 ? "Finish" : "Try it →",
            prevBtnText: "Back",
          },
        },
      ]);
      active.drive();
    };
    show(0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      active?.destroy();
    };
  }, [step]);
  const close = () => {
    save("welcome", "1");
    document.cookie = "dk-welcome=1; Path=/; Max-Age=31536000; SameSite=Lax";
    setWelcome(false);
  };
  const installNow = async () => {
    if (prompt.current) {
      await prompt.current.prompt();
      const choice = await prompt.current.userChoice;
      prompt.current = null;
      setInstall(false);
      if (choice.outcome === "accepted") setHint(false);
    } else if (ios) setHint(!hint);
  };
  return (
    <>
      {offline && (
        <div className="experience-banner" role="status">
          Offline ·{" "}
          {asOf ? "Showing saved data from " + asOf : "Showing saved data"}
        </div>
      )}
      {welcome && (
        <dialog
          className="welcome-sheet"
          open
          ref={modal}
          aria-label="Welcome to Market Studio"
          onCancel={close}
        >
          <div
            onTouchStart={(e) => (swipe.current = e.touches[0].clientX)}
            onTouchEnd={(e) => {
              const delta = e.changedTouches[0].clientX - swipe.current;
              if (Math.abs(delta) > 40)
                setPage(Math.min(2, Math.max(0, page + (delta < 0 ? 1 : -1))));
            }}
          >
            <div className={"welcome-art art-" + page} aria-hidden="true">
              {page === 0 ? (
                <img src="/brand/logo.svg" width="278" height="65" alt="" />
              ) : page === 1 ? (
                <div className="welcome-bars">
                  {[25, 43, 38, 60, 86].map((h, i) => (
                    <i style={{ height: h + "%" }} key={i} />
                  ))}
                </div>
              ) : (
                <span>✳</span>
              )}
            </div>
            <div className="welcome-copy">
              <small>Market Studio</small>
              <h2>{intro[page][0]}</h2>
              <p>{intro[page][1]}</p>
              <div className="welcome-pages">
                {intro.map((_, i) => (
                  <button
                    key={i}
                    aria-label={"Introduction " + (i + 1)}
                    aria-pressed={i === page}
                    onClick={() => setPage(i)}
                  >
                    <i />
                  </button>
                ))}
              </div>
              <div className="welcome-actions">
                <button onClick={close}>Skip</button>
                <button
                  className="tour-primary"
                  onClick={() => {
                    close();
                    setStep(0);
                  }}
                >
                  Take the 60-second tour
                </button>
              </div>
            </div>
          </div>
        </dialog>
      )}
      {coach && !offline && !welcome && step === null && (
        <aside className="market-coach">
          <span>{coaches[coach]}</span>
          <button aria-label="Dismiss tip" onClick={() => setCoach("")}>
            ×
          </button>
        </aside>
      )}
      {install && !welcome && step === null && (
        <button className="install-market" onClick={installNow}>
          Install app
        </button>
      )}
      {hint && (
        <div role="status" className="experience-banner">
          In Safari, open Share and choose Add to Home Screen.{" "}
          <button onClick={() => setHint(false)}>Dismiss</button>
        </div>
      )}
      {toast && (
        <div role="status" className="experience-banner">
          {toast}
        </div>
      )}
    </>
  );
}
