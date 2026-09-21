import unittest
from tools.run_eval_batches import remaining, errored, BatchRunner

SUMMARY = {"p": {"attempts": [{"ind": 1, "status": "SUCCESS"}, {"ind": 2, "status": "SUCCESS"}, {"ind": 3, "status": "x"}]}}


class EvalBatchTests(unittest.TestCase):
    def test_remaining_and_errored(self):
        store = {"p#1": {"identified": False}, "p#2": {"error": "boom"}}
        self.assertEqual(remaining(SUMMARY, store), 1)
        self.assertEqual(errored(store), ["p#2"])

    def test_runs_until_done(self):
        store = {}
        def batch(): store[f"p#{len(store) + 1}"] = {"identified": True}
        self.assertTrue(BatchRunner(batch, lambda: SUMMARY, lambda: store).run())

    def test_halts_on_error_and_on_no_progress(self):
        s1 = {}
        def bad(): s1["p#1"] = {"error": "x"}
        self.assertFalse(BatchRunner(bad, lambda: SUMMARY, lambda: s1).run())
        self.assertFalse(BatchRunner(lambda: None, lambda: SUMMARY, lambda: {}).run())


if __name__ == "__main__":
    unittest.main()
