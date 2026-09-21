import time, unittest
from tools.deadline import call_with_deadline
from tools.run_flaws_set import InsertError, Attempt, Config


def _quick(x): return x * 2
def _slow(): time.sleep(30)
def _boom(): raise ValueError("bad")


class DeadlineTests(unittest.TestCase):
    def test_returns_result_in_time(self):
        self.assertEqual(call_with_deadline(_quick, 5, 21), (True, 42))

    def test_terminates_a_runaway_call(self):
        t = time.time()
        self.assertEqual(call_with_deadline(_slow, 0.3), (False, None))
        self.assertLess(time.time() - t, 10)

    def test_child_errors_are_raised(self):
        with self.assertRaises(RuntimeError):
            call_with_deadline(_boom, 5)

    def test_insert_stage_reports_deadline_as_failed_insertion(self):
        stage = InsertError(deadline_s=7, runner=lambda fn, s, **k: (False, None))
        v = stage.run(Attempt("nonexistent_paper", 1, Config("t_deadline")))
        self.assertEqual((v.status, "deadline" in v.detail), ("insert_failed", True))


if __name__ == "__main__":
    unittest.main()
