import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "skills", "camera-roll", "scripts"))
sys.path.insert(0, os.path.join(REPO, "skills", "studio-protocol", "scripts"))

import camera_roll  # noqa: E402
import contracts  # noqa: E402
import provenance  # noqa: E402


class TestProvenanceAndNotes(unittest.TestCase):
    def test_ui_notes_flow_into_prompt_and_provenance_tracks_character_cascade(self):
        with tempfile.TemporaryDirectory() as td:
            bible_char = os.path.join(td, "bible", "characters", "rishi")
            cs_dir = os.path.join(td, "callsheets")
            dl_sc1 = os.path.join(td, "dailies", "EP01_SC01")
            dl_sc2 = os.path.join(td, "dailies", "EP01_SC02")
            os.makedirs(bible_char, exist_ok=True)
            os.makedirs(cs_dir, exist_ok=True)
            camera_roll.CONFIG["ledger"] = os.path.join(td, "reports", "ledger.csv")

            # Initial character bible v1
            front_png = os.path.join(bible_char, "front.png")
            with open(front_png, "wb") as f:
                f.write(b"RISHI_FACE_V1")
            with open(os.path.join(bible_char, "notes.md"), "w", encoding="utf-8") as f:
                f.write("# rishi\n\n## Lock (quote verbatim in prompts)\nYoung man in black hoodie, silver rimless glasses.\n")

            # Two scenes: SC01 (has rishi), SC02 (has rishi + another shot without rishi)
            sl1 = {
                "schema": "ShotList/1", "scene": "EP01_SC01", "aspect": "9:16", "style": "35mm", "audio": "hum",
                "shots": [{"id": "1A", "duration_s": 3, "camera": "MCU", "action": "Rishi looks up.", "characters": ["rishi"], "refs": [front_png]}],
            }
            sl2 = {
                "schema": "ShotList/1", "scene": "EP01_SC02", "aspect": "9:16", "style": "35mm", "audio": "hum",
                "shots": [
                    {"id": "2A", "duration_s": 3, "camera": "CU", "action": "Rishi opens door.", "characters": ["rishi"], "refs": [front_png]},
                    {"id": "2B", "duration_s": 3, "camera": "Wide", "action": "Empty hallway.", "characters": [], "refs": []},
                ],
            }
            with open(os.path.join(cs_dir, "EP01_SC01.shotlist.json"), "w") as f:
                json.dump(sl1, f)
            with open(os.path.join(cs_dir, "EP01_SC02.shotlist.json"), "w") as f:
                json.dump(sl2, f)

            # 1. Add a Director UI note on EP01_SC01/1A
            provenance.save_note(td, "EP01_SC01/1A", comment="Add rain reflection on his glasses", status="revise")

            # 2. Compile manifest & verify UI note is baked into the prompt
            man1 = contracts.compile_manifest(sl1, os.path.join(td, "bible"), dl_sc1, "EP01_SC01", production_dir=td)
            self.assertIn("Director notes (apply strictly): Add rain reflection on his glasses", man1[0]["prompt"])
            self.assertIn("silver rimless glasses", man1[0]["prompt"])

            # 3. Roll shot 1A in dry-run mode & inspect recorded provenance
            s = man1[0]
            camera_roll.roll(
                s["prompt"], s["out"], duration=s["duration"], aspect=s["aspect"],
                images=s["images"], shot_id=s["id"], dry_run=True,
                characters=s["characters"], scene=s["scene"], director_notes=s["director_notes"],
            )
            meta = provenance.inspect_asset(s["out"], production_dir=td)
            self.assertIsNotNone(meta)
            self.assertEqual(meta["prompt"], s["prompt"])
            self.assertEqual(meta["characters"], ["rishi"])
            self.assertEqual(meta["director_notes"], ["Add rain reflection on his glasses"])
            v1_hash = meta["refs"][0]["sha256_16"]
            self.assertIsNotNone(v1_hash)

            # 4. Director changes Rishi's character sheet (v2: removes glasses, leather jacket)
            with open(front_png, "wb") as f:
                f.write(b"RISHI_FACE_V2_NEW_LOOK")
            with open(os.path.join(bible_char, "notes.md"), "w", encoding="utf-8") as f:
                f.write("# rishi\n\n## Lock (quote verbatim in prompts)\nYoung man in brown leather jacket, no glasses.\n")

            # 5. Check character impact -> detects both scenes & flags 1A_take1.mp4 as stale!
            imp = provenance.impact_by_character(td, "rishi")
            self.assertEqual(imp["scenes"], ["EP01_SC01", "EP01_SC02"])
            self.assertEqual(len(imp["affected_shots"]), 2)  # 1A and 2A (not 2B!)
            self.assertEqual(len(imp["stale_takes"]), 1)
            self.assertIn("front.png changed", imp["stale_takes"][0]["reason"])

            # 6. Run cascade -> emits reroll manifest for 1A and 2A with the NEW character lock!
            reroll_p = os.path.join(td, "reroll_rishi.json")
            reroll = provenance.cascade_character(td, "rishi", reroll_p)
            self.assertEqual([x["id"] for x in reroll], ["1A", "2A"])
            self.assertIn("brown leather jacket, no glasses", reroll[0]["prompt"])
            self.assertIn("brown leather jacket, no glasses", reroll[1]["prompt"])


if __name__ == "__main__":
    unittest.main()
