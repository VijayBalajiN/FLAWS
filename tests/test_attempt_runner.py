import unittest
from tools.run_flaws_set import AttemptRunner, Verdict, Attempt, Config


class Pass:
    name = "pass"
    def run(self, a): return None

class Stop:
    name = "stop"
    def __init__(self, status): self.status = status; self.ran = False
    def run(self, a): self.ran = True; return Verdict(self.status)


class AttemptRunnerTests(unittest.TestCase):
    def test_first_verdict_short_circuits_later_stages(self):
        later = Stop("never")
        r = AttemptRunner([Pass(), Stop("filtered_easy"), later])
        self.assertEqual(r.run(Attempt("p", 1, Config("t"))).status, "filtered_easy")
        self.assertFalse(later.ran)

    def test_all_pass_is_no_verdict(self):
        self.assertEqual(AttemptRunner([Pass()]).run(Attempt("p", 1, Config("t"))).status, "no_verdict")

    def test_attempt_paths_are_per_paper_and_claim(self):
        a = Attempt("paperX", 3, Config("runZ"))
        self.assertIn("runZ/altered_papers/paperX/altered_3.tex", a.paths["tex"])


if __name__ == "__main__":
    unittest.main()
