import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "skills", "editor-assemble", "scripts"))
sys.path.insert(0, os.path.join(REPO, "skills", "sound-sfx", "scripts"))

import deliver  # noqa: E402
import grade  # noqa: E402
import sfx_synth  # noqa: E402


class TestPostPolish(unittest.TestCase):
    def test_deliver_reframe_auto_fill_vs_fit(self):
        vf_fill = deliver.build_reframe_vf(1920, 1080, 1080, 1920, mode="auto")
        self.assertIn("force_original_aspect_ratio=increase,crop=1080:1920", vf_fill)

        vf_fit = deliver.build_reframe_vf(720, 1280, 1080, 1920, mode="auto")
        self.assertIn("force_original_aspect_ratio=decrease,pad=1080:1920", vf_fit)

    def test_sfx_cues_from_edl(self):
        edl_txt = (
            "TITLE: EP01\nFCM: NON-DROP FRAME\n\n"
            "001  AX       AA/V  C        00:00:00:00 00:00:05:00 00:00:00:00 00:00:05:00\n"
            "002  AX       AA/V  D        00:00:00:00 00:00:04:00 00:00:05:00 00:00:09:00\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".edl", delete=False) as f:
            f.write(edl_txt)
            edl_path = f.name
        try:
            cues, length = sfx_synth.cues_from_edl(edl_path, room_tone_gain=0.15)
            self.assertEqual(length, 9.0)
            self.assertEqual(cues[0]["preset"], "room_tone")
            self.assertEqual(cues[1]["preset"], "whoosh_shimmer")
            self.assertAlmostEqual(cues[1]["t"], 4.85, places=2)
        finally:
            os.remove(edl_path)

    def test_grade_presets_exist_and_build_vf(self):
        for name, p in grade.LOOK_PRESETS.items():
            vf = grade.build_vf(p["exposure"], p["temp"], p["sat"], p["contrast"], p["gamma"], None, p["grain"])
            self.assertIn("eq=", vf, msg=name)


if __name__ == "__main__":
    unittest.main()
