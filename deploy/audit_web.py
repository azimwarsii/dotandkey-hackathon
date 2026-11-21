"""Measure default mobile Lighthouse performance and accessibility on the running web service."""

import json
import os
import statistics
import subprocess
import sys
from pathlib import Path


def main():
    origin = os.getenv("STUDIO_TEST_ORIGIN", "http://localhost:3000").rstrip("/")
    results = (
        Path(os.getenv("STUDIO_TEST_RESULTS", "/tmp/market-studio-smoke"))
        / "lighthouse"
    )
    results.mkdir(parents=True, exist_ok=True)
    scores = {"performance": [], "accessibility": []}
    failed_requests = []
    for run in range(1, 4):
        path = results / f"run-{run}.json"
        # Each CLI invocation starts a new Chrome profile with Lighthouse's default mobile throttling.
        subprocess.run(
            [
                "npx",
                "--yes",
                "lighthouse@13.6.0",
                origin + "/",
                "--quiet",
                "--chrome-flags=--headless --no-sandbox",
                "--only-categories=performance,accessibility",
                "--output=json",
                "--save-assets",
                "--output-path=" + str(path),
            ],
            check=True,
        )
        report = json.loads(path.read_text())
        if report.get("runtimeError"):
            raise RuntimeError(f"Run {run} failed: {report['runtimeError']['message']}")
        requests = report["audits"]["network-requests"]["details"]["items"]
        for request in requests:
            if request.get("statusCode", 0) >= 400:
                failed_requests.append(
                    {"run": run, "url": request["url"], "status": request["statusCode"]}
                )
        for category, samples in scores.items():
            score = report["categories"][category]["score"]
            if type(score) not in (float, int) or not 0 <= score <= 1:
                raise ValueError(f"Missing score for {category} in run {run}")
            samples.append(score * 100)
        print(
            f"Run {run}: performance {scores['performance'][-1]:g}, "
            f"accessibility {scores['accessibility'][-1]:g}",
            flush=True,
        )
    medians = {
        category: statistics.median(samples) for category, samples in scores.items()
    }
    (results / "summary.json").write_text(
        json.dumps(
            {"scores": scores, "medians": medians, "failedRequests": failed_requests},
            indent=2,
        )
        + "\n"
    )
    print(
        f"Median performance {medians['performance']:g}, accessibility {medians['accessibility']:g}"
    )
    if failed_requests:
        sys.exit(
            f"{len(failed_requests)} resource requests failed. Inspect the Lighthouse reports."
        )
    if min(medians.values()) < 90:
        sys.exit("Both mobile Lighthouse medians must reach 90.")


if __name__ == "__main__":
    main()
