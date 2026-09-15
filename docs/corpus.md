# The corpus

Seven papers. Five are AI/ML — the domain the benchmark is about. Two are
physical science, added deliberately: errors planted in a molecular-dynamics
or condensed-matter plan require domain knowledge that an AI-only corpus never
exercises, and they're readable by anyone who took undergrad physics or
chemistry.

| `paper_id` | Paper | Year | Source | Notes |
|---|---|---|---|---|
| `AttentionIsAllYouNeed` | Attention Is All You Need | 2017 | arXiv | Plan text reused directly from AIScientist |
| `BERT` | BERT: Pre-training of Deep Bidirectional Transformers | 2019 | arXiv | |
| `FLAWS` | The FLAWS benchmark paper | 2025 | arXiv | The method we forked |
| `SoundnessBench` | SoundnessBench | 2025 | arXiv | |
| `InnoEval` | InnoEval | 2026 | arXiv | |
| `McCammonProteinDynamics` | McCammon, Gelin & Karplus, *Dynamics of folded proteins*, Nature 267:585 | 1977 | [archive.bioinfo.se](https://archive.bioinfo.se/classical/papers_molmod/McCammon_1977.pdf) | The first protein MD simulation. See extraction note below. |
| `GrapheneFieldEffect` | Novoselov, Geim et al., *Electric Field Effect in Atomically Thin Carbon Films*, Science 306:666 | 2004 | [arXiv:cond-mat/0410550](https://arxiv.org/abs/cond-mat/0410550) | The graphene paper. Nobel 2010. |

GROBID only needs a PDF — no LaTeX source required, for any of these.

## Derived hypotheses

What the pipeline extracted as each paper's single falsifiable claim (this is
what the three typed hypothesis tracks attack):

- **McCammon** — *The interior of a folded globular protein is a fluid-like
  environment where local atomic motions exhibit a diffusional character.*
- **Graphene** — *Stable, atomically thin graphitic films are two-dimensional
  semimetals that exhibit a strong, ambipolar electric field effect, allowing
  the concentration of their charge carriers — both electrons and holes — to
  be tuned by an external gate voltage.*

Both are clean, specific, and falsifiable, which is what the whole method
depends on.

## Extraction note: the 1977 scan

The McCammon PDF is a **scan with no text layer** — page images only. GROBID
returned nothing usable and the PyPDF2 fallback returned an empty string.

Fix, in order:

1. `brew install ocrmypdf`
2. `ocrmypdf --force-ocr McCammonProteinDynamics.pdf <out>.pdf` — adds a text
   layer over the original page images
3. Extract with **PyPDF2 directly**, not GROBID

Step 3 is the non-obvious one. GROBID *did* succeed on the OCR'd file, but its
layout analysis fragmented words against the OCR'd glyph metrics — the title
came out as `Dyn ami cs of fold ed prot eins`. Raw PyPDF2 text was clean.

The tradeoff: PyPDF2 returns the whole paper including Results and Discussion,
which GROBID would have stripped. That turns out not to matter, because the
research-plan prompt already instructs the model to exclude results and
conclusions and write at proposal stage. Noisy word-splitting hurts
comprehension more than extra text does.

The resulting plan is faithful — correct model system (BPTI), correct method
(empirical potential energy function, extended-atom model), correct analysis
plan (r.m.s. fluctuations, time correlation functions).

Expect the same problem with any pre-~1990 paper. The recipe above generalises.

## Adding a paper

1. Get a PDF into `data/papers/pdfs/<PaperId>.pdf`. Prefer arXiv when a
   preprint exists — born-digital, clean text layer, no OCR step.
2. Check it has a text layer:
   ```bash
   python3 -c "import PyPDF2; print(len(PyPDF2.PdfReader('data/papers/pdfs/X.pdf').pages[0].extract_text() or ''))"
   ```
   Zero means scan → OCR first.
3. Run the three extraction steps in `docs/pipeline.md`.
4. **Read the generated plan.** The hypothesis in particular — if it's vague or
   unfalsifiable, everything downstream degrades and the typed tracks will
   flail.
5. Add the id to `ALL_PAPERS` in `src/pipeline/plan_error_insertion.py`.
