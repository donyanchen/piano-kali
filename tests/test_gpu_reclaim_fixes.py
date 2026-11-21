#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise atomic application, idempotence and fail-closed kernel patching.

The C context fixtures are from Linux v7.4-rc3's MSM driver (GPL-2.0-only).
They are patch contexts, not simulated GPU execution or hardware tests.
"""

import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest

PROJECT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gpu_reclaim_fixes", PROJECT / "tools/apply-gpu-reclaim-fixes.py")
FIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIX)

GPU = """static void retire_worker(struct kthread_work *work)
{
\tretire_submits(gpu);
}

/* call from irq handler to schedule work to retire bo's */
void msm_gpu_retire(struct msm_gpu *gpu)
{
\tint i;

\tfor (i = 0; i < gpu->nr_rings; i++)
\t\tmsm_update_fence(gpu->rb[i]->fctx, gpu->rb[i]->memptrs->fence);

\tkthread_queue_work(gpu->worker, &gpu->retire_work);
}

/* add bo's to gpu's ring, and kick gpu: */
"""

SHRINKER = """static bool can_swap(void)
{
\treturn enable_eviction && get_nr_swap_pages() > 0;
}

static bool can_block(struct shrink_control *sc)
{
\tif (!eviction_can_block)
\t\treturn false;
\treturn (sc->gfp_mask & __GFP_DIRECT_RECLAIM) ||
\t       (current_is_kswapd() && (sc->gfp_mask & __GFP_KSWAPD_RECLAIM));
}

static unsigned long
msm_gem_shrinker_count(void) { return 0; }
"""


class GpuReclaimFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.tree = self.root / "linux"
        drm = self.tree / "drivers/gpu/drm/msm"
        drm.mkdir(parents=True)
        self.gpu = drm / "msm_gpu.c"
        self.shrinker = drm / "msm_gem_shrinker.c"
        self.gpu.write_text(GPU)
        self.shrinker.write_text(SHRINKER)
        subprocess.run(["git", "init", "-q", str(self.tree)], check=True)
        self.manifest = self.root / "patches/gpu-reclaim-fixes.json"
        self.manifest.parent.mkdir()
        for source in FIX.DEFAULT_MANIFEST.parent.iterdir():
            if source.is_file():
                shutil.copy2(source, self.manifest.parent / source.name)

    def hashes(self):
        return [hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (self.gpu, self.shrinker)]

    def test_check_only_does_not_change_the_tree(self):
        before = self.hashes()
        result = FIX.apply_fixes(self.tree, self.manifest, check_only=True)
        self.assertEqual([p["status"] for p in result["patches"]], ["pending"] * 2)
        self.assertEqual(before, self.hashes())

    def test_apply_then_verify_is_idempotent(self):
        result = FIX.apply_fixes(self.tree, self.manifest)
        self.assertTrue(result["source_verified"])
        before = self.hashes()
        result = FIX.apply_fixes(self.tree, self.manifest, verify_only=True)
        self.assertEqual([p["status"] for p in result["patches"]], ["already_applied"] * 2)
        self.assertEqual(before, self.hashes())

    def test_already_applied_first_patch_is_not_duplicated(self):
        data = json.loads(self.manifest.read_text())
        patch = self.manifest.parent / data["patches"][0]["file"]
        subprocess.run(["git", "-C", str(self.tree), "apply", str(patch)], check=True)
        result = FIX.apply_fixes(self.tree, self.manifest)
        self.assertEqual([p["status"] for p in result["patches"]],
                         ["already_applied", "applied"])

    def test_bad_second_checksum_cannot_partially_patch_the_tree(self):
        data = json.loads(self.manifest.read_text())
        data["patches"][1]["sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(data))
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            FIX.apply_fixes(self.tree, self.manifest)
        self.assertEqual(before, self.hashes())

    def test_bad_second_context_cannot_partially_patch_the_tree(self):
        self.shrinker.write_text(SHRINKER.replace("get_nr_swap_pages() > 0", "false"))
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "cannot apply"):
            FIX.apply_fixes(self.tree, self.manifest)
        self.assertEqual(before, self.hashes())

    def test_verify_only_refuses_a_missing_fix(self):
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "missing required GPU"):
            FIX.apply_fixes(self.tree, self.manifest, verify_only=True)
        self.assertEqual(before, self.hashes())

    def test_semantic_guard_rejects_direct_reclaim_waits(self):
        FIX.apply_fixes(self.tree, self.manifest)
        self.shrinker.write_text(self.shrinker.read_text().replace(
            "return current_is_kswapd()", "return __GFP_DIRECT_RECLAIM || current_is_kswapd()"))
        with self.assertRaisesRegex(ValueError, "block direct reclaim"):
            FIX.verify_sources(self.tree)


if __name__ == "__main__":
    unittest.main()
