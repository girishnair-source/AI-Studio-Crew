import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "skills", "studio-protocol", "scripts"))

import contracts  # noqa: E402


class TestDirectionRules(unittest.TestCase):
    def test_callsheet_accepts_scene_purpose_and_turning_point(self):
        cs = dict(contracts.SKELETONS["CallSheet"])
        cs["brief"] = "Rishi receives an ominous call."
        cs["scene_purpose"] = {"function": "dynamic_shift", "summary": "Shifts power from Rishi to the unknown caller."}
        cs["turning_point"] = "Caller names Rishi's sister."
        errs = contracts.check(cs, "CallSheet")
        self.assertEqual(errs, [])

    def test_shotlist_enforces_intention_and_compiles_subtext_and_turning_point(self):
        sl = {
            "schema": "ShotList/1",
            "scene": "EP01_SC04",
            "format": "micro-drama",
            "aspect": "9:16",
            "style": "35mm gritty",
            "audio": "quiet room",
            "shots": [
                {
                    "id": "4A",
                    "duration_s": 6,
                    "is_turning_point": True,
                    "camera": "MCU push-in",
                    "action": "Rishi freezes as the caller speaks.",
                    "dialogue": [
                        {
                            "speaker": "caller",
                            "intention": "calm menace",
                            "objective": "force Rishi to stay on the line",
                            "subtext": "knows Rishi is terrified",
                            "line": "[cold] Don't hang up... *Rishi*.",
                        }
                    ],
                }
            ],
        }
        self.assertEqual(contracts.check(sl, "ShotList"), [])
        with tempfile.TemporaryDirectory() as td:
            man = contracts.compile_manifest(sl, td, td, "EP01_SC04")
        prompt = man[0]["prompt"]
        self.assertIn("turning point of the scene", prompt)
        self.assertIn("Objective: force Rishi to stay on the line", prompt)
        self.assertIn("Subtext: knows Rishi is terrified", prompt)

        sl_empty_int = json_copy(sl)
        sl_empty_int["shots"][0]["dialogue"][0]["intention"] = "   "
        errs = contracts.check(sl_empty_int, "ShotList")
        self.assertTrue(any("empty intention" in e for e in errs))

    def test_emotional_blocking_compiles_into_manifest(self):
        sl = {
            "schema": "ShotList/1",
            "scene": "EP01_SC04",
            "format": "micro-drama",
            "aspect": "9:16",
            "style": "35mm gritty",
            "audio": "quiet room",
            "shots": [
                {
                    "id": "4B",
                    "duration_s": 5,
                    "camera": "Locked static medium shot",
                    "action": "Rishi freezes by the doorway.",
                    "emotional_blocking": {
                        "power_dynamic": "Rishi trapped in narrow doorway off-center",
                        "movement_motivation": "shock stops him mid-step",
                        "stillness_accent": True,
                    },
                }
            ],
        }
        self.assertEqual(contracts.check(sl, "ShotList"), [])
        with tempfile.TemporaryDirectory() as td:
            man = contracts.compile_manifest(sl, td, td, "EP01_SC04")
        self.assertTrue(man[0]["stillness_accent"])
        self.assertIn("Spatial power: Rishi trapped in narrow doorway off-center", man[0]["prompt"])
        self.assertIn("Motivation: shock stops him mid-step", man[0]["prompt"])
        self.assertIn("Stillness: hold dead still", man[0]["prompt"])


def json_copy(obj):
    import json
    return json.loads(json.dumps(obj))


if __name__ == "__main__":
    unittest.main()
