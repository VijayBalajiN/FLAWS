import unittest
from tools.run_sets import chunk, problems, SetSequencer


class RunSetsTests(unittest.TestCase):
    def test_chunk(self):
        self.assertEqual(chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])

    def test_problems_ignores_normal_attrition(self):
        rec = {"attempts": [{"status": "filtered_easy"}, {"status": "self_identified"}], "final": "no_valid_error_within_budget"}
        self.assertEqual(problems(rec), [])
        self.assertEqual(problems({"attempts": [{"status": "compile_failed"}]}), ["compile_failed"])

    def test_sequencer_halts_on_problem_and_skips_done(self):
        summary, ran = {"a": {"n_claims": 3, "attempts": [{"status": "SUCCESS"}]}}, []
        def run_set(ps):
            ran.append(ps)
            for p in ps: summary[p] = {"n_claims": 3, "attempts": [{"status": "compile_failed" if p == "c" else "SUCCESS"}]}
        ok = SetSequencer(run_set, lambda: summary, 7, 1).run([["a", "b"], ["c", "d"], ["e", "f"]])
        self.assertFalse(ok)
        self.assertEqual(ran, [["b"], ["c", "d"]])


if __name__ == "__main__":
    unittest.main()
