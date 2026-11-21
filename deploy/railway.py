#!/usr/bin/env python3
"""Provision and deploy this repository into its dedicated Railway project."""

import argparse
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "dotandkey-market-studio"
ENV = "production"
REPO = "azimwarsii/dotandkey-hackathon"
CLIPFORGE = "bded6ceaa46649068e8da5882d7c29fd8c977a3b"
CLI = ["npx", "--yes", "@railway/cli@5.75.0"]
DOCKERFILES = {
    "api": "Dockerfile.api",
    "web": "studio-web/Dockerfile",
    "cron": "deploy/Dockerfile.cron",
}
WATCH = {
    "api": [
        "/market_intel/**",
        "/requirements*.txt",
        "/Dockerfile.api",
        "/deploy/start_api.py",
        "/data/*.sqlite3",
        "/data/studio/runs/watermelon-demo/**",
        "/lexicons/**",
        "/vendor/**",
        "/validation/aspect_precision.json",
        "/.dockerignore",
    ],
    "web": ["/studio-web/**", "/.dockerignore"],
    "cron": ["/deploy/Dockerfile.cron", "/deploy/nightly.sh", "/.dockerignore"],
}


def railway(*args, cwd, secret=None):
    result = subprocess.run(
        [*CLI, *args, "--json"], cwd=cwd, input=secret, text=True, capture_output=True
    )
    if result.returncode:
        # Commands receiving secrets never echo their diagnostics or arguments.
        detail = (
            "Railway variable update failed."
            if secret is not None
            else result.stderr.strip()
        )
        raise SystemExit(detail or f"Railway {args[0]} failed.")
    return json.loads(result.stdout) if result.stdout.strip() else None


def project_for(work):
    teams = railway("whoami", cwd=work)["workspaces"]
    selected = os.environ.get("RAILWAY_WORKSPACE")
    teams = [t for t in teams if not selected or selected in (t["name"], t["id"])]
    if len(teams) != 1:
        raise SystemExit("Set RAILWAY_WORKSPACE to the intended Railway workspace ID.")
    workspace = teams[0]["id"]
    matches = [
        p
        for p in railway("list", cwd=work)
        if p["name"] == PROJECT and p["workspace"]["id"] == workspace
    ]
    if len(matches) > 1:
        raise SystemExit(f"More than one project is named {PROJECT} in this workspace.")
    if not matches:
        return railway("init", "--name", PROJECT, "--workspace", workspace, cwd=work)[
            "id"
        ]
    project = matches[0]["id"]
    railway(
        "link",
        "--project",
        project,
        "--workspace",
        workspace,
        "--environment",
        ENV,
        cwd=work,
    )
    return project


def configure(project, work):
    scope = ["--project", project, "--environment", ENV]
    names = {s["name"] for s in railway("service", "list", *scope, cwd=work)}
    for name in ["api", "clipforge", "web", "cron"]:
        if name not in names:
            railway("add", "--service", name, cwd=work)

    volumes = railway("volume", *scope, "list", cwd=work)["volumes"]
    for name, path in [("api", "/app/data"), ("clipforge", "/data")]:
        existing = [v["mountPath"] for v in volumes if v["serviceName"] == name]
        if existing and existing != [path]:
            raise SystemExit(
                f"{name} has an existing volume at an unexpected mount path."
            )
        if not existing:
            railway(
                "volume",
                *scope,
                "--service",
                name,
                "add",
                "--mount-path",
                path,
                cwd=work,
            )

    edits = []
    for name in ("api", "clipforge", "web", "cron"):
        settings = {
            "deploy.restartPolicyType": "NEVER" if name == "cron" else "ON_FAILURE"
        }
        if name in DOCKERFILES:
            settings.update(
                {
                    "build.builder": "DOCKERFILE",
                    "build.dockerfilePath": DOCKERFILES[name],
                    "build.watchPatterns": json.dumps(WATCH[name]),
                }
            )
        if name == "cron":
            settings["deploy.cronSchedule"] = "45 21 * * *"
        else:
            settings["deploy.healthcheckPath"] = "/" if name == "web" else "/api/health"
        for key, value in settings.items():
            edits.extend(["--service-config", name, key, value])
    railway(
        "environment",
        "edit",
        *scope,
        *edits,
        "--message",
        "Configure Market Studio services",
        cwd=work,
    )

    domains = railway("domain", "list", *scope, "--service", "web", cwd=work)["domains"]
    web_domains = [d["domain"] for d in domains if d["type"] == "service"]
    if web_domains:
        return "https://" + web_domains[0]
    return railway("domain", *scope, "--service", "web", "--port", "3000", cwd=work)[
        "domain"
    ]


def has_credit_limit(key):
    req = Request(
        "https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer " + key}
    )
    try:
        with urlopen(req, timeout=15) as response:
            limit = json.load(response)["data"]["limit"]
        return type(limit) in (int, float) and math.isfinite(limit) and limit >= 0
    except (OSError, ValueError, KeyError):
        return False


def variables(project, work, origin, commit):
    scope = ["--project", project, "--environment", ENV]
    local = {**dotenv_values(ROOT / ".env"), **os.environ}
    current_api = railway("variable", "list", "--service", "api", *scope, cwd=work)
    cron_token = current_api.get("JOBS_CRON_TOKEN") or secrets.token_urlsafe(36)
    api = {
        "APP_REVISION": commit,
        "PORT": "8000",
        "CLIPFORGE_URL": "http://${{clipforge.RAILWAY_PRIVATE_DOMAIN}}:3000",
        "STUDIO_GRID_CALLBACK_HOST": "${{api.RAILWAY_PRIVATE_DOMAIN}}",
        "STUDIO_GRID_BIND_HOST": "::",
        "STUDIO_PUBLIC_ORIGIN": origin,
        "STUDIO_TRUST_PROXY": "1",
        "JOBS_CRON_TOKEN": cron_token,
    }
    for key in (
        "CRUSTDATA_API_KEY",
        "SARVAM_API_KEY",
        "YOUTUBE_API_KEY",
        "SCRAPECREATORS_API_KEY",
    ):
        if local.get(key):
            api[key] = local[key]
    key_name = "OPENROUTER_API_KEY"
    for candidate in dict.fromkeys([local.get(key_name), current_api.get(key_name)]):
        if candidate and has_credit_limit(candidate):
            api[key_name] = candidate
            break
    else:
        if current_api.get(key_name):
            railway(
                "variable", "delete", key_name, "--service", "api", *scope, cwd=work
            )
        print(
            "OpenRouter generation is disabled until a credit-limited key is available.",
            flush=True,
        )

    backend = "http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000"
    values = {
        "api": api,
        "web": {"PORT": "3000", "STUDIO_BACKEND": backend},
        "clipforge": {"PORT": "3000", "HOSTNAME": "::"},
        "cron": {
            "STUDIO_BACKEND": backend,
            "JOBS_CRON_TOKEN": "${{api.JOBS_CRON_TOKEN}}",
        },
    }
    for service, pairs in values.items():
        for name, value in pairs.items():
            railway(
                "variable",
                "set",
                name,
                "--stdin",
                "--service",
                service,
                *scope,
                "--skip-deploys",
                cwd=work,
                secret=value,
            )


def snapshot(commit, work):
    source = work / "source"
    source.mkdir()
    # Archive only tracked, committed project files. Ignore local data and credentials.
    archive = work / "source.tar"
    subprocess.run(["git", "archive", "-o", archive, commit], cwd=ROOT, check=True)
    subprocess.run(["tar", "-xf", archive, "-C", source], check=True)
    for required in DOCKERFILES.values():
        if not (source / required).is_file():
            raise SystemExit(f"Commit {required} before deploying this revision.")
    clip = work / "clipforge"
    subprocess.run(["git", "init", "-q", clip], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            clip,
            "fetch",
            "-q",
            "--depth=1",
            "https://github.com/xixihhhh/clipforge.git",
            CLIPFORGE,
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", clip, "checkout", "-q", "--detach", CLIPFORGE], check=True
    )
    return source, clip


def deploy(project, work, source, clip, commit):
    pending = {}
    for service in ("api", "clipforge", "cron", "web"):
        directory = clip if service == "clipforge" else source
        result = railway(
            "up",
            str(directory),
            "--path-as-root",
            "--detach",
            "--service",
            service,
            "--environment",
            ENV,
            "--project",
            project,
            "--message",
            "Market Studio " + commit[:12],
            cwd=work,
        )
        pending[service] = result["deploymentId"]
        print(f"{service} queued ({pending[service]}).", flush=True)
    deadline = time.monotonic() + 3600
    while pending and time.monotonic() < deadline:
        for service, deployment_id in list(pending.items()):
            rows = railway(
                "deployment",
                "list",
                "--service",
                service,
                "--environment",
                ENV,
                "--project",
                project,
                cwd=work,
            )
            status = next((r["status"] for r in rows if r["id"] == deployment_id), None)
            if status in {"SUCCESS", "COMPLETED"} or (
                service == "cron" and status == "SLEEPING"
            ):
                del pending[service]
                print(f"{service} deployed.", flush=True)
            elif status in {
                "FAILED",
                "CRASHED",
                "REMOVED",
                "CANCELED",
                "NEEDS_APPROVAL",
                "SKIPPED",
            }:
                raise SystemExit(
                    f"{service} deployment {deployment_id} ended with {status}. Inspect Railway logs."
                )
        if pending:
            time.sleep(10)
    if pending:
        raise SystemExit("Timed out waiting for " + ", ".join(pending))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--connect-main",
        action="store_true",
        help="also enable GitHub auto-deploy from main",
    )
    args = parser.parse_args()
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if args.connect_main:
        remote = subprocess.check_output(
            ["git", "ls-remote", f"https://github.com/{REPO}", "refs/heads/main"],
            text=True,
        ).split()[0]
        if remote != commit:
            raise SystemExit(
                "Merge this revision into the remote main branch before connecting auto-deploy."
            )
    with tempfile.TemporaryDirectory(prefix="market-studio-") as tmp:
        work = Path(tmp)
        source, clip = snapshot(commit, work)
        project = project_for(work)
        origin = configure(project, work)
        variables(project, work, origin, commit)
        deploy(project, work, source, clip, commit)
        if args.connect_main:
            for service in DOCKERFILES:
                railway(
                    "service",
                    "source",
                    "connect",
                    "--repo",
                    REPO,
                    "--branch",
                    "main",
                    "--service",
                    service,
                    "--project",
                    project,
                    "--environment",
                    ENV,
                    cwd=work,
                )
        for path in [
            "/",
            "/api/health",
            "/studio-api/runs/watermelon-demo",
            "/manifest.webmanifest",
            "/sw.js",
        ]:
            with urlopen(origin + path, timeout=60) as response:
                if response.status != 200:
                    raise SystemExit(f"HTTPS verification failed for {path}.")
        print("Market Studio is live at " + origin)


if __name__ == "__main__":
    main()
