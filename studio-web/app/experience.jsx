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
const coaches = {
  studio: "Paste a reel on the Research step, or open a saved reference.",
  products: "Choose a product to compare its marketplace listings.",
  strategy: "Open an evidence card to see the sources behind a recommendation.",
};
export default function AppExperience({
  startTour,
  exitTour,
  step,
  view,
  asOf: reportDate,
  welcomeInitially,
}) {
  const [welcome, setWelcome] = useState(!!welcomeInitially),
    modal = useRef(null);
  const [offline, setOffline] = useState(false),
    [asOf, setAsOf] = useState(""),
    [install, setInstall] = useState(false),
    [ios, setIos] = useState(false),
    [hint, setHint] = useState(false),
    [coach, setCoach] = useState("");
  const [toast, setToast] = useState("");
  const prompt = useRef(null);
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
      setCoach("");
      exitTour();
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
          <div className="welcome-art" aria-hidden="true">
            <img src="/brand/logo.svg" width="278" height="65" alt="" />
          </div>
          <div className="welcome-copy">
            <small>Market Studio</small>
            <h2>From a product to a campaign</h2>
            <p>
              Search the catalog, open customer reviews and explore how a Dot
              &amp; Key campaign becomes a video. You’ll use the real workspace
              and a saved example.
            </p>
            <div className="welcome-actions">
              <button onClick={close}>Skip</button>
              <button
                className="tour-primary"
                onClick={() => {
                  close();
                  startTour();
                }}
              >
                Start interactive walkthrough →
              </button>
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
