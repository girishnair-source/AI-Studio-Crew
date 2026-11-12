import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "skills", "editor-assemble", "scripts"))
sys.path.insert(0, os.path.join(REPO, "skills", "studio-protocol", "scripts"))

import assemble  # noqa: E402
import contracts  # noqa: E402


class TestAssemble(unittest.TestCase):
    def test_atempo_chain(self):
        self.assertEqual(assemble._atempo_chain(1.0), [])
        self.assertEqual(assemble._atempo_chain(1.5), ["atempo=1.5000"])
        self.assertEqual(assemble._atempo_chain(3.0), ["atempo=2.0", "atempo=1.5000"])
        self.assertEqual(assemble._atempo_chain(0.25), ["atempo=0.5", "atempo=0.5000"])

    def test_write_ass_captions_karaoke_and_pop(self):
        with tempfile.TemporaryDirectory() as td:
            ass = os.path.join(td, "caps.ass")
            assemble.write_ass_captions(
                [
                    {"from": 0.2, "to": 1.8, "text": "Hello world", "mode": "karaoke"},
                    {"from": 2.0, "to": 3.0, "text": "Cut!", "mode": "pop"},
                ],
                ass,
                720,
                1280,
            )
            with open(ass, encoding="utf-8") as f:
                txt = f.read()
            self.assertIn("PlayResX: 720", txt)
            self.assertIn("{\\kf", txt)
            self.assertIn("{\\fscx92", txt)

    def test_assemble_end_to_end_jcut_broll_speed_captions(self):
        with tempfile.TemporaryDirectory() as td:
            c1 = os.path.join(td, "c1.mp4")
            c2 = os.path.join(td, "c2.mp4")
            br = os.path.join(td, "br.mp4")
            for p, color, freq in ((c1, "red", 440), (c2, "green", 550), (br, "yellow", 660)):
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-loglevel", "error",
                        "-f", "lavfi", "-i", f"color=c={color}:s=360x640:r=24:d=2",
                        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", p,
                    ],
                    check=True,
                )
            cut_json = os.path.join(td, "cut.json")
            out_mp4 = os.path.join(td, "out.mp4")
            with open(cut_json, "w") as f:
                json.dump(
                    {
                        "fps": 24,
                        "width": 360,
                        "height": 640,
                        "clips": [
                            {"src": "c1.mp4", "in": 0, "out": 2.0, "broll": [{"src": "br.mp4", "in": 0, "at": 0.5, "dur": 1.0, "mode": "pip"}]},
                            {"src": "c2.mp4", "in": 0, "out": 2.0, "speed": 1.25, "audio_lead_s": 0.4},
                        ],
                        "captions": [{"from": 0.2, "to": 1.5, "text": "Testing captions", "mode": "karaoke"}],
                    },
                    f,
                )
            subprocess.run(
                [sys.executable, os.path.join(REPO, "skills", "editor-assemble", "scripts", "assemble.py"), "--cut", cut_json, "--out", out_mp4, "--otio"],
                check=True,
            )
            self.assertTrue(os.path.exists(out_mp4))
            self.assertTrue(os.path.exists(out_mp4 + ".edl"))
            self.assertTrue(os.path.exists(out_mp4 + ".otio"))
            self.assertTrue(os.path.exists(out_mp4 + ".changes.json"))
            # Expected duration = 2.0 + (2.0 / 1.25) = 3.6s
            d = assemble.dur(out_mp4)
            self.assertAlmostEqual(d, 3.6, delta=0.15)

    def test_compile_cut_from_shotlist_and_summary(self):
        sl = {
            "scene": "EP01_SC04",
            "aspect": "9:16",
            "shots": [{"id": "4A", "duration_s": 6}, {"id": "4B", "duration_s": 5, "transition": "dissolve"}],
        }
        summ = {
            "locked_takes": [
                {"shot": "4A", "take": "/tmp/4A_take1.mp4", "trim_to": 5.4},
                {"shot": "4B", "take": "/tmp/4B_take1.mp4"},
            ]
        }
        cut = contracts.compile_cut(sl, summ, "/tmp/cuts/cut.json")
        self.assertEqual(cut["width"], 1080)
        self.assertEqual(cut["height"], 1920)
        self.assertEqual(len(cut["clips"]), 2)
        self.assertEqual(cut["clips"][0]["out"], "speech")
        self.assertEqual(cut["clips"][1]["out"], 5)


if __name__ == "__main__":
    unittest.main()
