#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Apply checksum-pinned MSM reclaim fixes to the prepared kernel tree."""

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

PROJECT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT / "kernel/patches/gpu-reclaim-fixes.json"


def git(tree, *args):
    return subprocess.run(
        ["git", "-C", str(tree), *args], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def function_body(source, name):
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    match = re.search(r"\b" + re.escape(name) + r"\s*\([^)]*\)\s*\{", source)
    if not match:
        raise ValueError(f"missing kernel function: {name}")
    depth = 1
    for end in range(match.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[match.end():end]
    raise ValueError(f"unclosed kernel function: {name}")


def verify_sources(tree):
    drm = tree / "drivers/gpu/drm/msm"
    retire = function_body((drm / "msm_gpu.c").read_text(), "msm_gpu_retire")
    shrink = function_body((drm / "msm_gem_shrinker.c").read_text(), "can_block")
    if not re.search(r"\bsignal_completed_submits\s*\(", retire):
        raise ValueError("GPU retire path does not signal completed hardware fences")
    if "__GFP_DIRECT_RECLAIM" in shrink or "current_is_kswapd" not in shrink:
        raise ValueError("MSM shrinker can still block direct reclaim")
    if "eviction_can_block" not in shrink:
        raise ValueError("MSM eviction_can_block runtime switch was lost")


def apply_fixes(tree, manifest, *, check_only=False, verify_only=False):
    manifest = manifest.resolve()
    data = json.loads(manifest.read_text())
    if data.get("version") != 1 or not data.get("patches"):
        raise ValueError("unsupported or empty GPU patch manifest")
    entries = []
    # Verify every input before editing any source file.
    for item in data["patches"]:
        patch = (manifest.parent / item["file"]).resolve()
        if not patch.is_relative_to(manifest.parent):
            raise ValueError("patch path escapes its manifest directory")
        if not re.fullmatch(r"[0-9a-f]{40}", item["commit"]):
            raise ValueError("patch commit must be an immutable SHA")
        actual = hashlib.sha256(patch.read_bytes()).hexdigest()
        if actual != item["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {patch.name}")
        entries.append((item, patch))

    pending, statuses = [], []
    for item, patch in entries:
        if git(tree, "apply", "--reverse", "--check", str(patch)).returncode == 0:
            state = "already_applied"
        else:
            result = git(tree, "apply", "--check", str(patch))
            if result.returncode:
                raise ValueError(f"cannot apply {patch.name}: {result.stderr.strip()}")
            state = "pending"
            pending.append(patch)
        statuses.append({**item, "status": state})

    if verify_only and pending:
        raise ValueError("kernel is missing required GPU reclaim fixes")
    if pending:
        # Check the whole pending set before applying any of it. Do not use
        # --reject or conflict-favouring merge strategies for these fixes.
        result = git(tree, "apply", "--check", *(str(p) for p in pending))
        if result.returncode:
            raise ValueError(f"GPU patch preflight failed: {result.stderr.strip()}")
        if not check_only:
            result = git(tree, "apply", *(str(p) for p in pending))
            if result.returncode:
                raise ValueError(f"GPU patch application failed: {result.stderr.strip()}")
            for item in statuses:
                if item["status"] == "pending":
                    item["status"] = "applied"
    if not check_only or not pending:
        verify_sources(tree)
    return {"version": 1, "patches": statuses,
            "source_verified": not check_only or not pending,
            "hardware_validation": "NOT_PERFORMED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-tree", type=pathlib.Path, required=True)
    parser.add_argument("--manifest", type=pathlib.Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=pathlib.Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        result = apply_fixes(args.kernel_tree.resolve(), args.manifest,
                             check_only=args.check_only, verify_only=args.verify_only)
        output = json.dumps(result, indent=2) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(output)
        print(output, end="")
    except (OSError, ValueError, KeyError) as error:
        print(f"GPU reclaim fix refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
