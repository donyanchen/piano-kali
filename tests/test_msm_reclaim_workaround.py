# SPDX-License-Identifier: GPL-2.0-only
"""Verify rollback behaviour using temporary files, never live GPU settings."""

import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

PROJECT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "msm_workaround", PROJECT / "tools/msm-reclaim-workaround.py")
FIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIX)


class MsmWorkaroundTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = pathlib.Path(temporary.name)
        self.parameter, self.state, self.model = (root / n for n in ("parameter", "state", "model"))
        self.parameter.write_text("Y\n")
        self.model.write_text("Xiaomi Pad 8 Pro\x00")
        for name, value in (("PARAMETER", self.parameter), ("STATE", self.state), ("MODEL", self.model)):
            override = patch.object(FIX, name, value)
            override.start()
            self.addCleanup(override.stop)

    def test_repeated_apply_keeps_the_first_rollback_value(self):
        FIX.change("apply")
        FIX.change("apply")
        self.assertEqual(json.loads(self.state.read_text())["original"], "Y")
        self.assertEqual(self.parameter.read_text().strip(), "N")
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)

    def test_restore_reinstates_the_original_value(self):
        FIX.change("apply")
        result = FIX.change("restore")
        self.assertTrue(result["restored"])
        self.assertEqual(self.parameter.read_text().strip(), "Y")
        self.assertFalse(self.state.exists())

    def test_different_kernel_cannot_apply_or_restore_stale_state(self):
        self.state.write_text(json.dumps({"kernel_release": "other-kernel", "original": "Y"}))
        for mode in ("apply", "restore"):
            with self.assertRaises(ValueError):
                FIX.change(mode)
            self.assertEqual(self.parameter.read_text().strip(), "Y")

    def test_other_device_is_refused_without_a_parameter_write(self):
        self.model.write_text("another tablet")
        with self.assertRaisesRegex(ValueError, "scoped"):
            FIX.change("apply")
        self.assertEqual(self.parameter.read_text().strip(), "Y")
        self.assertFalse(self.state.exists())

    def test_status_does_not_create_a_rollback_record(self):
        result = FIX.change("status")
        self.assertEqual(result["eviction_can_block"], "Y")
        self.assertFalse(self.state.exists())
