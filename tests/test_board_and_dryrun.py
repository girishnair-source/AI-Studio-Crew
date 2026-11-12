import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "skills", "camera-roll", "scripts"))
sys.path.insert(0, os.path.join(REPO, "skills", "dailies-qc", "scripts"))

import camera_roll  # noqa: E402
import dailies_qc  # noqa: E402


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

            emb_board = dailies_qc.build_board(td, out=os.path.join(td, "emb.html"), embed=True)
            with open(emb_board, encoding="utf-8") as f:
                self.assertIn("data:image/png;base64,", f.read())


if __name__ == "__main__":
    unittest.main()
