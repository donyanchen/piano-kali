#!/usr/bin/env python3
"""Fetch pinned sheng assets; reject kernel binaries with incorrect SHA-256."""
import hashlib
import json
import pathlib
import sys
import urllib.request

project = pathlib.Path(__file__).resolve().parents[1]
lock = json.loads((project / "configs/sources.json").read_text())
assets = pathlib.Path(sys.argv[1]).resolve()
assets.mkdir(parents=True, exist_ok=True)


def fetch(url, path, sha256=None):
    if not path.exists():
        print(f"Downloading {path.name}", flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": "sheng-kali-builder"})
        temporary = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(request, timeout=120) as source, temporary.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        temporary.replace(path)
    digest_state = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest_state.update(chunk)
    digest = digest_state.hexdigest()
    if sha256 and digest != sha256:
        raise SystemExit(f"SHA-256 mismatch: {path}")
    print(f"Verified {path.name}: {digest}", flush=True)


for name, digest in lock["kernel_assets"].items():
    fetch(f"https://github.com/{lock['kernel_repository']}/releases/download/"
          f"{lock['kernel_release']}/{name}", assets / name, digest)
for kind in ("firmware", "adaptation"):
    fetch(f"https://codeload.github.com/{lock[kind + '_repository']}/tar.gz/"
          f"{lock[kind + '_commit']}", assets / f"{kind}.tar.gz", lock[kind + "_sha256"])
for name, asset in lock.get("extra_assets", {}).items():
    fetch(asset["url"], assets / name, asset["sha256"])
