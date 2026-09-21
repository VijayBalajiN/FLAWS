import os, tempfile, unittest
from src.utils.latex_to_pdf import plan_bibliography, build_steps, BibliographyPlan, ensure_bbl_fallback


class BibliographyPlanTests(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp()

    def touch(self, name, d=None):
        open(os.path.join(d or self.d, name), "w").close()

    def test_bibtex_when_bib_present(self):
        self.touch("refs.bib")
        self.assertEqual(plan_bibliography(r"\bibliography{refs}", self.d).engine, "bibtex")

    def test_no_engine_when_bib_missing(self):
        self.assertIsNone(plan_bibliography(r"\bibliography{refs}", self.d).engine)

    def test_commented_bibliography_ignored(self):
        self.touch("refs.bib")
        self.assertIsNone(plan_bibliography("% \\bibliography{refs}\n", self.d).engine)

    def test_biber_for_biblatex(self):
        self.touch("refs.bib")
        self.assertEqual(plan_bibliography(r"\addbibresource{refs.bib}", self.d).engine, "biber")

    def test_steps_include_bib_only_when_planned(self):
        cmd = ["pdflatex"]
        self.assertEqual(len(build_steps(BibliographyPlan(None), cmd, "m")), 3)
        self.assertEqual(len(build_steps(BibliographyPlan("bibtex"), cmd, "m")), 4)

    def test_bbl_fallback_copies_shipped_bbl(self):
        src, build = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.touch("orig.bbl", src)
        ensure_bbl_fallback(src, build, "altered_1")
        self.assertTrue(os.path.exists(os.path.join(build, "altered_1.bbl")))


if __name__ == "__main__":
    unittest.main()
