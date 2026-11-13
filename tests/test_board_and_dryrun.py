import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "skills", "camera-roll", "scripts"))
sys.path.insert(0, os.path.join(REPO, "skills", "dailies-qc", "scripts"))
sys.path.insert(0, os.path.join(REPO, "skills", "studio-protocol", "scripts"))

import camera_roll  # noqa: E402
import dailies_qc  # noqa: E402
import studio_board  # noqa: E402


class TestBoardAndDryRun(unittest.TestCase):
    def test_dry_run_roll_to_dailies_board_e2e(self):
        with tempfile.TemporaryDirectory() as td:
            camera_roll.CONFIG["ledger"] = os.path.join(td, "ledger.csv")
            take1 = os.path.join(td, "4A_take1.mp4")
            res = camera_roll.roll("Test shot", take1, duration="3s", aspect="9:16", dry_run=True, shot_id="4A")
            self.assertEqual(res["lane"], "dry-run")
            self.assertTrue(os.path.exists(take1))

            rep = dailies_qc.scene(td, no_llm=True)
            self.assertIn("4A_take1.mp4", rep)
            board = os.path.join(td, "dailies_board.html")
            self.assertTrue(os.path.exists(board))
            with open(board, encoding="utf-8") as f:
                html = f.read()
            self.assertIn("Shot 4A", html)
            self.assertIn("4A_take1.mp4", html)
            self.assertIn("<video ", html)

            emb_board = dailies_qc.build_board(td, out=os.path.join(td, "emb.html"), embed=True)
            with open(emb_board, encoding="utf-8") as f:
                self.assertIn("data:image/png;base64,", f.read())

    def test_script_screenplay_storyboard_and_hub_boards(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            cs_dir = os.path.join(td, "callsheets")
            os.makedirs(cs_dir, exist_ok=True)
            script_txt = "INT. BEDROOM - NIGHT\n\nRishi stares at his phone.\n\nCALLER\n[cold] Don't hang up... *Rishi*.\n"
            script_p = os.path.join(td, "ep01.fountain")
            with open(script_p, "w", encoding="utf-8") as f:
                f.write(script_txt)

            bd_p = os.path.join(cs_dir, "EP01_breakdown.json")
            with open(bd_p, "w", encoding="utf-8") as f:
                json.dump({"episode": "EP01", "scenes": [{"scene": "SC01", "heading": "INT. BEDROOM - NIGHT", "characters": {"CALLER": 5}, "estimated_seconds": 8, "estimated_clips": 1}]}, f)

            cs_p = os.path.join(cs_dir, "EP01_SC01.callsheet.json")
            with open(cs_p, "w", encoding="utf-8") as f:
                json.dump({"scene": "EP01_SC01", "mode": "dailies", "scene_purpose": {"function": "dynamic_shift", "summary": "Caller takes control"}, "turning_point": "Caller names Rishi"}, f)

            sl_p = os.path.join(cs_dir, "EP01_SC01.shotlist.json")
            with open(sl_p, "w", encoding="utf-8") as f:
                json.dump({
                    "schema": "ShotList/1", "scene": "EP01_SC01", "aspect": "9:16", "style": "35mm gritty", "audio": "quiet",
                    "shots": [{
                        "id": "1A", "duration_s": 6, "is_turning_point": True, "camera": "MCU push-in", "action": "Rishi freezes.",
                        "emotional_blocking": {"power_dynamic": "Rishi cornered", "stillness_accent": True},
                        "dialogue": [{"speaker": "CALLER", "intention": "calm menace", "objective": "trap him", "subtext": "watching him", "line": "[cold] Don't hang up... *Rishi*."}],
                    }],
                }, f)

            sc_html = studio_board.build_script_board(bd_p)
            sp_html = studio_board.build_screenplay_board(script_p, shotlist_paths=[sl_p])
            sb_html = studio_board.build_storyboard_board([sl_p], os.path.join(td, "sb.html"))
            hub_html = studio_board.build_hub(td, episode="EP01", script_path=script_p)

            for path, needle in ((sc_html, "Caller takes control"), (sp_html, "Objective:"), (sb_html, "Turning Point"), (hub_html, "4. Dailies (Video)")):
                self.assertTrue(os.path.exists(path))
                with open(path, encoding="utf-8") as f:
                    self.assertIn(needle, f.read())


if __name__ == "__main__":
    unittest.main()
