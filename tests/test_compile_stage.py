import unittest
from tools.run_flaws_set import CompilePdf, Attempt, Config


class CompileStageTests(unittest.TestCase):
    def attempt(self):
        return Attempt("paperX", 1, Config("t"))

    def stage(self, baseline_ok):
        return CompilePdf(compiler=lambda **k: "/nonexistent/x.pdf", baseline_ok=lambda p: baseline_ok)

    def test_failed_build_with_good_baseline_is_blamed_on_insertion(self):
        self.assertEqual(self.stage(True).run(self.attempt()).status, "insertion_broke_latex")

    def test_failed_build_with_broken_baseline_is_a_tooling_failure(self):
        self.assertEqual(self.stage(False).run(self.attempt()).status, "compile_failed")


if __name__ == "__main__":
    unittest.main()
