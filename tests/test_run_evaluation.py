import os, tempfile, unittest
from tools.run_evaluation import Target, Verdict, targets_from_summary, read_verdicts, EvalStore, Evaluator


class EvaluationTests(unittest.TestCase):
    def test_targets_only_include_successful_attempts(self):
        s = {"p": {"attempts": [{"ind": 1, "status": "SUCCESS"}, {"ind": 2, "status": "self_identified"}]}}
        self.assertEqual(targets_from_summary(s), [Target("p", 1)])

    def test_read_verdicts_combines_metrics_with_or(self):
        d = tempfile.mkdtemp()
        open(f"{d}/p_1_m_score.txt", "w").write("lev")
        open(f"{d}/p_1_m_comparison.txt", "w").write("judge")
        v = read_verdicts(d, "m", Target("p", 1), 10, 0.5, lambda t, k, threshold: False, lambda t, k: True)
        self.assertEqual(v, Verdict(True, False, True))

    def test_store_persists_and_evaluator_skips_done_and_records_errors(self):
        d = tempfile.mkdtemp(); store = EvalStore(f"{d}/e.json"); calls = []
        ev = Evaluator(lambda t: calls.append(t), lambda t: Verdict(False, False, False), store)
        ev.run(Target("p", 1)); ev.run(Target("p", 1))
        self.assertEqual(len(calls), 1)
        self.assertFalse(EvalStore(f"{d}/e.json").data["p#1"]["identified"])
        bad = Evaluator(lambda t: 1 / 0, lambda t: None, store); bad.run(Target("q", 2))
        self.assertIn("ZeroDivisionError", store.data["q#2"]["error"])
        self.assertFalse(store.done(Target("q", 2)))


if __name__ == "__main__":
    unittest.main()
