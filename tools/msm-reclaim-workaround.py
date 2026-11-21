#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Temporarily disable blocking MSM eviction on piano; retain a rollback value."""

import argparse
import json
import os
import pathlib
import re
import sys

PARAMETER = pathlib.Path("/sys/module/msm/parameters/eviction_can_block")
STATE = pathlib.Path("/run/piano-msm-reclaim-workaround.json")
MODEL = pathlib.Path("/sys/firmware/devicetree/base/model")


def read_value():
    value = PARAMETER.read_text().strip().upper()
    if value not in ("Y", "N"):
        raise ValueError("unexpected MSM boolean value")
    return value


def write_value(value):
    PARAMETER.write_text(value + "\n")
    if read_value() != value:
        raise ValueError("MSM parameter readback did not match")


def change(mode):
    model = MODEL.read_text().strip("\x00\n")
    if "xiaomipad8pro" not in re.sub(r"[^a-z0-9]", "", model.lower()):
        raise ValueError("this workaround is scoped to Xiaomi Pad 8 Pro / piano")
    release = os.uname().release
    before = read_value()
    if mode == "status":
        return {"kernel_release": release, "eviction_can_block": before,
                "rollback_saved": STATE.exists()}
    if mode == "apply":
        if STATE.exists():
            saved = json.loads(STATE.read_text())
            if saved.get("kernel_release") != release:
                raise ValueError("rollback record belongs to a different kernel")
            if saved.get("original") not in ("Y", "N"):
                raise ValueError("invalid original value in rollback record")
        else:
            saved = {"kernel_release": release, "original": before}
            descriptor = os.open(STATE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                json.dump(saved, stream)
                stream.write("\n")
        write_value("N")
        return {"kernel_release": release, "eviction_can_block": "N",
                "original": saved["original"], "temporary_until_reboot": True}
    saved = json.loads(STATE.read_text())
    if saved.get("kernel_release") != release or saved.get("original") not in ("Y", "N"):
        raise ValueError("rollback record does not match this kernel")
    write_value(saved["original"])
    STATE.unlink()
    return {"kernel_release": release, "eviction_can_block": saved["original"],
            "restored": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("status", "apply", "restore"))
    args = parser.parse_args()
    if os.geteuid() != 0:
        print("Root permission is required for the protected MSM parameter.", file=sys.stderr)
        return 1
    try:
        print(json.dumps(change(args.mode), indent=2))
    except (OSError, ValueError) as error:
        print(f"MSM workaround refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
