import os, tempfile, unittest
from tools.archive_attempts import archive_failed, attempt_files


class ArchiveTests(unittest.TestCase):
    def test_moves_only_failed_attempts_and_keeps_successes(self):
        base = tempfile.mkdtemp()
        for d, name in [("inserted_error", "p_1_m.txt"), ("inserted_error", "p_2_m.txt"), ("altered_papers/p", "altered_1.tex")]:
            os.makedirs(f"{base}/{d}", exist_ok=True); open(f"{base}/{d}/{name}", "w").write("x")
        rec = {"attempts": [{"ind": 1, "status": "self_identified"}, {"ind": 2, "status": "SUCCESS"}]}
        self.assertEqual(archive_failed(base, "p", rec, "r1"), 1)
        self.assertEqual([a["ind"] for a in rec["attempts"]], [2])
        self.assertEqual(rec["archived"][0]["archive_tag"], "r1")
        self.assertTrue(os.path.exists(f"{base}/_archive/r1/inserted_error/p_1_m.txt"))
        self.assertTrue(os.path.exists(f"{base}/inserted_error/p_2_m.txt"))
        self.assertEqual(attempt_files(base, "p", 1), [])


if __name__ == "__main__":
    unittest.main()
