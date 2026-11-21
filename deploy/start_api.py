"""Seed a fresh persistent volume before serving the private API."""

import fcntl
import os
from pathlib import Path
import shutil
import socket


def seed_volume(source, volume):
    volume.mkdir(parents=True, exist_ok=True)
    with (volume / ".seed.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        marker = volume / ".seeding"
        if not marker.exists():
            if any(
                p.name not in {".seed.lock", "lost+found"} for p in volume.iterdir()
            ):
                return
            marker.touch()

        # Publish only complete files. A restart resumes a partially copied seed.
        for src in source.rglob("*"):
            dest = volume / src.relative_to(source)
            if src.is_dir():
                dest.mkdir(exist_ok=True)
            elif not dest.exists():
                tmp = dest.with_name(dest.name + ".seed-tmp")
                shutil.copyfile(src, tmp)
                os.replace(tmp, dest)
        marker.rename(volume / ".seeded")


if __name__ == "__main__":
    import uvicorn

    from market_intel.frontend_api.cache import warm

    seed_volume(Path("/app/seed-data"), Path("/app/data"))
    warm(print)
    port = int(os.environ.get("PORT", "8000"))
    config = uvicorn.Config(
        "market_intel.api:app", host="::", port=port, proxy_headers=False
    )
    # asyncio's implicit IPv6 listener is IPv6-only on Linux. Compose uses IPv4 DNS.
    with socket.create_server(
        ("::", port), family=socket.AF_INET6, dualstack_ipv6=True
    ) as listener:
        uvicorn.Server(config).run(sockets=[listener])
