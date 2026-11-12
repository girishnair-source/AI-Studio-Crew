import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "skills", "dailies-qc", "scripts"))
sys.path.insert(0, os.path.join(REPO, "skills", "studio-protocol", "scripts"))

import dailies_qc  # noqa: E402
import retake_governor  # noqa: E402


class TestDailiesQC(unittest.TestCase):
    def test_strip_stage_tags(self):
        line = "[whisper] Wait... *don't* hang up! [pause]"
        self.assertEqual(dailies_qc.strip_stage_tags(line), ["wait", "don", "t", "hang", "up"])

    def test_compute_wer_exact_and_mismatch(self):
        exact = dailies_qc.compute_wer("[slow] Hello world!", "Hello, world.")
        self.assertEqual(exact["wer"], 0.0)
        self.assertEqual(exact["word_accuracy"], 1.0)
        self.assertEqual(exact["missing_words"], [])

        mismatch = dailies_qc.compute_wer("Check the lock on the door", "Check lock door")
        self.assertGreater(mismatch["wer"], 0.25)
        self.assertEqual(mismatch["missing_words"], ["the", "on", "the"])

    def test_asr_check_flags_mismatch_and_hallucination(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as vid:
            with mock.patch("dailies_qc.subprocess.run") as m_run, \
                 mock.patch("dailies_qc._gemini_qc_call") as m_llm:
                def fake_ffmpeg(cmd, **kw):
                    # Create empty wav file at the last argument path
                    open(cmd[-1], "wb").write(b"RIFF0000")
                    return mock.MagicMock(returncode=0)

                m_run.side_effect = fake_ffmpeg
                m_llm.return_value = {"transcript": "Hello", "language": "en", "intelligible": True}
                res = dailies_qc.asr_check(vid.name, expected_text="Hello my dear friend tonight")
                self.assertIn("dialogue-mismatch", res["flags"])

                m_llm.return_value = {"transcript": "Random background words", "language": "en", "intelligible": True}
                res2 = dailies_qc.asr_check(vid.name, expected_text="")
                self.assertIn("hallucinated-speech", res2["flags"])

    def test_visual_check_flags(self):
        with tempfile.NamedTemporaryFile(suffix=".png") as contact, \
             tempfile.NamedTemporaryFile(suffix=".png") as ref:
            with mock.patch("dailies_qc._gemini_qc_call") as m_llm:
                m_llm.return_value = {
                    "face_consistency": 2,
                    "wardrobe_consistency": 5,
                    "unprompted_captions": True,
                    "morphing_or_artifacts": False,
                    "action_match": True,
                    "issues": ["face drifted in frame 4", "burned-in yellow subtitles"],
                }
                res = dailies_qc.visual_check(contact.name, refs=[ref.name], expected_action="Rishi answers phone")
                self.assertIn("face-drift", res["flags"])
                self.assertIn("unprompted-captions", res["flags"])
                self.assertNotIn("continuity-drift", res["flags"])

    def test_full_qc_with_real_synthetic_clip_no_llm(self):
        with tempfile.TemporaryDirectory() as td:
            mp4 = os.path.join(td, "test_take1.mp4")
            subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "color=c=blue:s=360x640:r=24:d=3",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", mp4,
                ],
                check=True,
            )
            res = dailies_qc.full_qc(mp4, no_llm=True)
            self.assertTrue(os.path.exists(res["contact"]))
            self.assertTrue(os.path.exists(res["last_frame"]))
            self.assertEqual(res["visual_basic"]["width"], 360)
            self.assertEqual(res["visual_basic"]["height"], 640)
            self.assertIn("frozen-video", res["flags"])  # solid blue frame for 3s triggers frozen-video

    def test_retake_governor_autofix_new_flags(self):
        for flag in ("dialogue-mismatch", "face-drift", "unprompted-captions", "visual-artifacts", "frozen-video"):
            p, d, note = retake_governor.auto_fix("Base prompt", flag, 1, 6)
            self.assertIsNotNone(p, f"missing auto_fix for {flag}")
            self.assertIsNotNone(note)
            self.assertEqual(d, 6)


if __name__ == "__main__":
    unittest.main()
