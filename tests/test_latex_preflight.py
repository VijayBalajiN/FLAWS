import os, tempfile, unittest
from tools.latex_preflight import required_packages, missing_packages, first_latex_error


class LatexPreflightTests(unittest.TestCase):
    def test_required_packages_parses_options_lists_and_ignores_comments(self):
        tex = "\\usepackage[utf8]{inputenc}\n\\usepackage{a, b}\n% \\usepackage{commented}\n\\RequirePackage{c}"
        self.assertEqual(required_packages(tex), ["a", "b", "c", "inputenc"])

    def test_missing_packages_uses_injected_lookup_and_local_files(self):
        d = tempfile.mkdtemp(); open(os.path.join(d, "shipped.sty"), "w").close()
        tex = "\\usepackage{CJK,shipped,amsmath}"
        got = missing_packages(tex, d, exists=lambda f: f == "amsmath.sty")
        self.assertEqual(got, ["CJK"])

    def test_first_latex_error(self):
        f = os.path.join(tempfile.mkdtemp(), "l.log")
        open(f, "w").write("ok\n! LaTeX Error: File `CJK.sty' not found.\n! later\n")
        self.assertIn("CJK.sty", first_latex_error(f))
        self.assertEqual(first_latex_error(f + "x"), "")


if __name__ == "__main__":
    unittest.main()
