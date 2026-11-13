import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "skills", "camera-roll", "scripts"))
sys.path.insert(0, os.path.join(REPO, "skills", "studio-protocol", "scripts"))

import camera_roll  # noqa: E402
import retake_governor  # noqa: E402


class TestLoopGuardrails(unittest.TestCase):
    def test_camera_roll_caps_failed_soft_refusal_at_one_retry(self):
        calls = []

        def fake_roll_once(ln, prompt, out, **kw):
            calls.append(ln)
            raise camera_roll.RollError("failed", "completed but no video in response")

        with mock.patch("camera_roll.roll_once", side_effect=fake_roll_once), \
             mock.patch("camera_roll.time.sleep"):
            with self.assertRaises(camera_roll.RollError) as ctx:
                camera_roll.roll("prompt", "/tmp/out.mp4")
        self.assertEqual(ctx.exception.kind, "failed")
        # 1 initial + 1 retry = 2 total attempts (NOT 2 lanes * 3 retries = 6!)
        self.assertEqual(len(calls), 2)

    def test_camera_roll_enforces_wall_clock_deadline(self):
        orig_wall = camera_roll.CONFIG["max_roll_wall_s"]
        try:
            camera_roll.CONFIG["max_roll_wall_s"] = 5
            with mock.patch("camera_roll.roll_once", side_effect=camera_roll.RollError("capacity", "429")), \
                 mock.patch("camera_roll.time.sleep"):
                with self.assertRaises(camera_roll.RollError) as ctx:
                    camera_roll.roll("prompt", "/tmp/out.mp4")
            # backoff_s[0] is 8s > max_roll_wall_s 5s -> aborts immediately on first backoff check!
            self.assertEqual(ctx.exception.kind, "timeout")
        finally:
            camera_roll.CONFIG["max_roll_wall_s"] = orig_wall

    def test_governor_does_not_multiply_failed_rolls_and_blocks_chained_children(self):
        with tempfile.TemporaryDirectory() as td:
            shots = [
                {"id": "4A", "prompt": "parent", "duration": "4s"},
                {"id": "4B", "prompt": "child", "duration": "4s", "chain_from": "4A"},
                {"id": "4C", "prompt": "grandchild", "duration": "4s", "chain_from": "4B"},
            ]
            roll_calls = []

            def fake_roll(prompt, out, **kw):
                roll_calls.append(kw.get("shot_id"))
                raise camera_roll.RollError("failed", "soft refusal")

            with mock.patch("retake_governor.roll", side_effect=fake_roll):
                results, budget, _ = retake_governor.execute_scene(shots, "EP01_SC04", td, max_auto=2, max_rolls=12)

            # 4A escalates immediately on take 1 (no 3x loop!), and 4B + 4C are blocked without rolling!
            self.assertEqual(len(roll_calls), 1)
            by_shot = {r["shot"]: r["status"] for r in results}
            self.assertEqual(by_shot, {"4A": "escalate", "4B": "blocked", "4C": "blocked"})

    def test_governor_binds_winning_parent_take_last_frame_for_chained_child(self):
        with tempfile.TemporaryDirectory() as td:
            shots = [
                {"id": "4A", "prompt": "parent", "duration": "4s", "dialogue": "hello"},
                {"id": "4B", "prompt": "child", "duration": "4s", "chain_from": "4A", "images": [os.path.join(td, "4A_take1_last.png")]},
            ]
            seen_images = {}

            def fake_roll(prompt, out, **kw):
                open(out, "wb").write(b"MP4")
                seen_images[kw.get("shot_id")] = list(kw.get("images", []))
                return {"out": out}

            # 4A fails QC on take 1 ('monotone-read'), passes on take 2 -> 4B must bind 4A_take2_last.png!
            qc_seq = [{"flags": ["monotone-read"], "trim_to": 3.5}, {"flags": [], "trim_to": 3.5}, {"flags": [], "trim_to": 3.5}]
            with mock.patch("retake_governor.roll", side_effect=fake_roll), \
                 mock.patch("retake_governor.qc_take", side_effect=qc_seq), \
                 mock.patch("retake_governor.last_frame", side_effect=lambda v, o: open(o, "wb").write(b"PNG")):
                results, budget, _ = retake_governor.execute_scene(shots, "EP01_SC04", td, max_auto=2, max_rolls=12)

            by_shot = {r["shot"]: r["status"] for r in results}
            self.assertEqual(by_shot, {"4A": "ok", "4B": "ok"})
            self.assertEqual(seen_images["EP01_SC04/4B/t1"][0], os.path.join(td, "4A_take2_last.png"))

    def test_governor_thread_safe_roll_budget_never_overshoots(self):
        with tempfile.TemporaryDirectory() as td:
            shots = [{"id": f"S{i}", "prompt": "p", "duration": "3s", "dialogue": "hi"} for i in range(10)]

            def fake_roll(prompt, out, **kw):
                open(out, "wb").write(b"MP4")
                return {"out": out}

            with mock.patch("retake_governor.roll", side_effect=fake_roll), \
                 mock.patch("retake_governor.qc_take", return_value={"flags": ["monotone-read"]}), \
                 mock.patch("retake_governor.last_frame"):
                results, budget, _ = retake_governor.execute_scene(shots, "EP01_SC04", td, max_auto=2, max_rolls=5, parallel=6)

            self.assertEqual(budget["rolls"], 5)


if __name__ == "__main__":
    unittest.main()
