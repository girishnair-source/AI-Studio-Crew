import base64
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "skills", "camera-roll", "scripts"))

import camera_roll  # noqa: E402


class TestCameraRoll(unittest.TestCase):
    def test_extract_usage(self):
        resp = {
            "usage": {
                "total_input_tokens": 1200,
                "total_output_tokens": 48000,
                "output_tokens_by_modality": {"video": 45200},
            }
        }
        u = camera_roll.extract_usage(resp)
        self.assertEqual(u["gen_tokens"], 45200)
        self.assertEqual(u["llm_in"], 1200)
        self.assertEqual(u["llm_out"], 48000)

    def test_normalize_duration_lane_bounds(self):
        self.assertEqual(camera_roll.normalize_duration("7s", camera_roll.CONFIG["lanes"]["omni-1.2"]), "7s")
        self.assertEqual(camera_roll.normalize_duration("6", camera_roll.CONFIG["lanes"]["veo-3.1"]), "6s")
        with self.assertRaises(camera_roll.RollError):
            camera_roll.normalize_duration("12s", camera_roll.CONFIG["lanes"]["veo-3.1"])

    def test_roll_interactions_extracts_usage_and_writes_video(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "clip.mp4")
            camera_roll.CONFIG["lanes"]["omni-1.2"]["project"] = "test-proj"
            camera_roll.CONFIG["ledger"] = os.path.join(td, "ledger.csv")
            fake_bytes = base64.b64encode(b"MP4DATA").decode()
            with mock.patch("camera_roll.get_token", return_value="tok"), \
                 mock.patch("camera_roll._http") as m_http:
                m_http.side_effect = [
                    {"id": "int-1", "status": "in_progress"},
                    {
                        "id": "int-1",
                        "status": "completed",
                        "usage": {"total_input_tokens": 500, "total_output_tokens": 15000, "output_tokens_by_modality": {"video": 14300}},
                        "outputs": [{"content": [{"type": "video", "data": fake_bytes}]}],
                    },
                ]
                with mock.patch("camera_roll.time.sleep"):
                    res = camera_roll.roll_once("omni-1.2", "test prompt", out, duration="7s")
            self.assertEqual(res["gen_tokens"], 14300)
            self.assertEqual(res["llm_in"], 500)
            self.assertTrue(os.path.exists(out))
            with open(out, "rb") as f:
                self.assertEqual(f.read(), b"MP4DATA")

    def test_roll_veo_adapter(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "veo.mp4")
            ref = os.path.join(td, "ref.png")
            with open(ref, "wb") as f:
                f.write(b"PNGDATA")
            camera_roll.CONFIG["lanes"]["veo-3.1-fast"]["project"] = "test-proj"
            camera_roll.CONFIG["ledger"] = os.path.join(td, "ledger.csv")
            fake_bytes = base64.b64encode(b"VEOMP4").decode()
            with mock.patch("camera_roll.get_token", return_value="tok"), \
                 mock.patch("camera_roll._http") as m_http:
                m_http.side_effect = [
                    {"name": "projects/test-proj/locations/us-central1/operations/op1"},
                    {"done": True, "response": {"videos": [{"bytesBase64Encoded": fake_bytes}]}},
                ]
                with mock.patch("camera_roll.time.sleep"):
                    res = camera_roll.roll_once("veo-3.1-fast", "car chase", out, duration="6s", images=[ref])
            self.assertEqual(res["lane"], "veo-3.1-fast")
            self.assertTrue(os.path.exists(out))
            # Verify predictLongRunning and fetchPredictOperation URLs were called
            self.assertIn(":predictLongRunning", m_http.call_args_list[0][0][1])
            self.assertIn(":fetchPredictOperation", m_http.call_args_list[1][0][1])

    def test_promote_clip_upscale_vs_reroll(self):
        with mock.patch("camera_roll.roll") as m_roll:
            camera_roll.promote_clip("draft.mp4", "hero.mp4", resolution="1080p", method="upscale")
            self.assertEqual(m_roll.call_args.kwargs["task"], "upscale")
            self.assertEqual(m_roll.call_args.kwargs["video"], "draft.mp4")
            self.assertEqual(m_roll.call_args.kwargs["resolution"], "1080p")

            camera_roll.promote_clip("draft.mp4", "hero2.mp4", resolution="4k", method="reroll", prompt="scene", images=["a.png"])
            self.assertEqual(m_roll.call_args.kwargs["task"], "reference_to_video")
            self.assertEqual(m_roll.call_args.kwargs["resolution"], "4k")

    def test_local_setup_config_persists_outside_repo(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = os.path.join(td, "config.json")
            orig_path = camera_roll.LOCAL_CONFIG_PATH
            try:
                camera_roll.LOCAL_CONFIG_PATH = cfg_path
                camera_roll.setup_config(project="my-gcp-proj", lane="veo-3.1-fast")
                loaded = camera_roll.load_local_config()
                self.assertEqual(loaded["project"], "my-gcp-proj")
                self.assertEqual(loaded["default_lane"], "veo-3.1-fast")
                self.assertEqual(camera_roll.CONFIG["lanes"]["omni-1.2"]["project"], "my-gcp-proj")
            finally:
                camera_roll.LOCAL_CONFIG_PATH = orig_path


if __name__ == "__main__":
    unittest.main()
