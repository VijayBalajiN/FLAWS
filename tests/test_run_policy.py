import unittest
from tools.run_policy import count_successes, budget_exhausted, is_satisfied, final_label


def rec(statuses, n_claims=8, final=None):
    return {"attempts": [{"status": s} for s in statuses], "n_claims": n_claims, "final": final}


class RunPolicyTests(unittest.TestCase):
    def test_needs_min_errors_not_just_one(self):
        self.assertFalse(is_satisfied(rec(["filtered_easy", "SUCCESS"]), 2, 7))
        self.assertTrue(is_satisfied(rec(["SUCCESS", "self_identified", "SUCCESS"]), 2, 7))

    def test_satisfied_when_budget_or_claims_exhausted(self):
        self.assertTrue(is_satisfied(rec(["filtered_easy"] * 7), 2, 7))
        self.assertTrue(is_satisfied(rec(["filtered_easy"] * 3, n_claims=3), 2, 7))
        self.assertFalse(is_satisfied(rec(["filtered_easy"] * 3), 2, 7))

    def test_no_claims_is_terminal(self):
        self.assertTrue(is_satisfied({"final": "no_claims", "attempts": []}, 2, 7))

    def test_labels(self):
        self.assertEqual(final_label(rec(["SUCCESS", "SUCCESS"]), 2), "SUCCESS")
        self.assertEqual(final_label(rec(["SUCCESS", "filtered_easy"]), 2), "PARTIAL")
        self.assertEqual(final_label(rec(["filtered_easy"]), 2), "no_valid_error_within_budget")
        self.assertEqual(count_successes(rec(["SUCCESS", "x", "SUCCESS"])), 2)


if __name__ == "__main__":
    unittest.main()
