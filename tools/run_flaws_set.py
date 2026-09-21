"""Run the ORIGINAL FLAWS single-paper insertion pipeline on a small set of papers, cost-guarded.

The upstream step functions (src/pipeline/single_process/single_error_insertion.py) are reused
unchanged. This driver only adds orchestration:
  * each pipeline step is a `Stage` (one responsibility, common interface) so steps can be
    added/reordered without editing the runner (SRP/OCP/LSP);
  * `AttemptRunner` walks the stages for one (paper, claim) and stops at the first verdict;
  * `RunStore` is the only thing that touches run_summary.json (persistence apart from logic);
  * a per-paper cap on claims tried, since upstream leaves retrying to the human.
Usage: python -m tools.run_flaws_set --papers arxiv_a arxiv_b [--version run1] [--max-claims 3]
"""
import argparse, faulthandler, json, os, random, sys, time, traceback
from dataclasses import dataclass, field
from typing import Protocol

sys.path.insert(0, os.getcwd())

from tools.deadline import call_with_deadline
from tools.run_policy import (DEFAULT_MAX_CLAIMS, DEFAULT_MIN_ERRORS, count_successes,
                              is_satisfied, final_label)
from src.pipeline.single_process import single_error_insertion as S
from src.utils import llm_calls
from src.utils.formatting import format_claims, format_generated_error, format_localized_error
from src.utils.prompts import (generate_claim_prompt, generate_error_generation_prompt,
    generate_filter_invalid_error_prompt, generate_filter_easy_error_prompt,
    generate_error_location_prompt, generate_internal_error_identification_prompt)
from src.utils.evaluation_helpers import parse_levenshtein
from src.utils.latex_to_pdf import (combine_latex_sources, compile_latex,
    check_pdf_for_unresolved_references, compress_pdf_ghostscript)


@dataclass(frozen=True)
class Config:
    version: str
    model_family: str = "gemini"
    model: str = "gemini-2.5-pro"
    hallucination_threshold: float = 0.9   # same defaults as upstream __main__
    levenshtein_threshold: float = 0.5
    top_k: int = 10


@dataclass(frozen=True)
class Verdict:
    status: str
    detail: str = ""


@dataclass
class Attempt:
    """Everything one (paper, claim) attempt needs: identity plus derived file locations."""
    paper: str
    ind: int
    cfg: Config
    paths: dict = field(init=False)

    def __post_init__(self):
        v, m, p, i = self.cfg.version, self.cfg.model, self.paper, self.ind
        base = f"data/{v}"
        self.paths = dict(
            latex=f"data/papers/{p}/combined.tex",
            claims=f"{base}/generated_claims/{p}_{m}.txt",
            error_folder=f"{base}/inserted_error", location_folder=f"{base}/location_error",
            identify_folder=f"{base}/identified_errors",
            err=f"{base}/inserted_error/{p}_{i}_{m}.txt",
            filter=f"{base}/inserted_error/{p}_{i}_{m}_filter.txt",
            tex=f"{base}/altered_papers/{p}/altered_{i}.tex",
            loc=f"{base}/location_error/{p}_{i}_{m}.txt",
            idfile=f"{base}/identified_errors/{p}_{i}_{m}.txt",
            score=f"{base}/identified_errors/{p}_{i}_{m}_score.txt",
            build_dir=f"/data/{v}/altered_papers/{p}")

    def llm(self):  # kwargs shared by every upstream step function
        return dict(paper=self.paper, model_family=self.cfg.model_family, model=self.cfg.model, ind=self.ind)


class Stage(Protocol):
    name: str
    def run(self, a: Attempt) -> Verdict | None: ...   # None = pass, continue


class GenerateError:
    name = "generate"
    def run(self, a):
        P = a.paths
        if not os.path.exists(P["err"]):
            S.generate_error(prompt=generate_error_generation_prompt, claim_file=P["claims"],
                             error_folder=P["error_folder"], latex_file=P["latex"], **a.llm())
        mod, orig, _, _ = format_generated_error(P["err"])
        # an untagged generation would parse to [""] and be "inserted" at char 0
        if not (mod and orig and mod[0].strip() and orig[0].strip()) or len(mod) != len(orig) or mod == orig:
            return Verdict("bad_generation", "untagged/empty/identical modified vs original text")


class FilterErrors:
    name = "filter"
    def run(self, a):
        P = a.paths
        if os.path.exists(P["filter"]):  # resumed: honour the stored verdict
            if "No changes required" not in open(P["filter"]).read():
                return Verdict("filtered", "(stored verdict)")
            return None
        for status, prompt in (("filtered_invalid", generate_filter_invalid_error_prompt),
                               ("filtered_easy", generate_filter_easy_error_prompt)):
            if S.filter_error(prompt=prompt, error_folder=P["error_folder"], error_filename=P["err"],
                              latex_file=P["latex"], **a.llm()):
                return Verdict(status)


class InsertError:
    """Insert the generated error into the LaTeX. Upstream's fuzzy matcher is O(n*m) and can run for
    hours on a long paper, so it gets a hard deadline; overrunning counts as a failed insertion."""
    name = "insert"

    def __init__(self, deadline_s: float = 300, runner=call_with_deadline):
        self.deadline_s, self.runner = deadline_s, runner

    def run(self, a):
        P = a.paths
        if os.path.exists(P["tex"]):
            return None
        done, out = self.runner(S.insert_error, self.deadline_s, paper=a.paper, error_filename=P["err"],
                                version_control=a.cfg.version, latex_file=P["latex"], ind=a.ind,
                                threshold=a.cfg.hallucination_threshold)
        if not done:
            return Verdict("insert_failed", f"fuzzy match exceeded {self.deadline_s:.0f}s deadline")
        if out is None:
            return Verdict("insert_failed", "original text mismatch (hallucinated excerpt)")


class LocalizeError:
    name = "localize"
    def run(self, a):
        P = a.paths
        if not os.path.exists(P["loc"]):
            S.localize_error(prompt=generate_error_location_prompt, error_folder=P["location_folder"],
                             error_filename=P["err"], latex_file=P["tex"], **a.llm())


class SelfIdentify:
    name = "self_identify"
    def run(self, a):
        P, cfg = a.paths, a.cfg
        mod, orig, _, _ = format_generated_error(P["err"])
        if not os.path.exists(P["idfile"]):
            spans = [len(x.split()) for x in mod + format_localized_error(P["loc"]) + orig]
            S.internal_identify_error(prompt=generate_internal_error_identification_prompt,
                                      identify_folder=P["identify_folder"], latex_file=P["tex"],
                                      num_chunks=cfg.top_k, word_limit=max(spans), **a.llm())
        if os.path.exists(P["score"]):
            found = bool(parse_levenshtein(open(P["score"]).read(), cfg.top_k, threshold=cfg.levenshtein_threshold))
        else:
            found = S.internal_evaluate_error(
                paper=a.paper, error_location_filename=P["loc"], internal_identify_error_filename=P["idfile"],
                identified_error_folder=P["identify_folder"], modified_text=mod, model=cfg.model, ind=a.ind,
                threshold=cfg.levenshtein_threshold, generate_k=cfg.top_k)
        if found:
            return Verdict("self_identified", "internal identification found it (too easy)")


def preflight_baseline_ok(paper: str) -> bool:
    """The unmodified paper compiled during preflight (tools/fetch_and_preflight.py)."""
    return os.path.exists(f"data/_preflight/{paper}/altered_pre.pdf")


class CompilePdf:
    """Compile the altered paper (no API cost).

    A failed build is blamed on the *insertion* when the unmodified paper is known to compile
    (typically the fuzzy match ate neighbouring \\end{...} lines), which is ordinary attrition;
    only when the baseline is also broken is it reported as a tooling `compile_failed`."""
    name = "compile"

    def __init__(self, compiler=compile_latex, baseline_ok=preflight_baseline_ok):
        self.compiler, self.baseline_ok = compiler, baseline_ok

    def run(self, a):
        pdf = self.compiler(paper=a.paper, des=a.paths["build_dir"], main_tex=a.paths["tex"])
        if not os.path.exists(pdf):
            log = f"{a.paths['build_dir'].lstrip('/')}/latex_compilation_log.txt"
            status = "insertion_broke_latex" if self.baseline_ok(a.paper) else "compile_failed"
            return Verdict(status, f"see {log}")
        if not check_pdf_for_unresolved_references(pdf):
            return Verdict("unresolved_refs", pdf)
        small = pdf.replace(".pdf", "_small.pdf")
        if not os.path.exists(small):
            compress_pdf_ghostscript(pdf, small)
        return Verdict("SUCCESS", pdf)


DEFAULT_STAGES: list[Stage] = [GenerateError(), FilterErrors(), InsertError(), LocalizeError(), SelfIdentify(), CompilePdf()]


class AttemptRunner:
    """Runs stages in order for one attempt; the first stage that returns a Verdict ends it."""
    def __init__(self, stages: list[Stage] = DEFAULT_STAGES):
        self.stages = stages

    def run(self, a: Attempt) -> Verdict:
        for stage in self.stages:
            verdict = stage.run(a)
            if verdict:
                return verdict
        return Verdict("no_verdict")


class RunStore:
    """Persistence for run_summary.json - the only class that reads/writes it."""
    def __init__(self, path: str):
        self.path = path
        self.data = json.load(open(path)) if os.path.exists(path) else {}

    def paper(self, name: str) -> dict:
        return self.data.setdefault(name, {"attempts": []})

    def save(self) -> None:
        json.dump(self.data, open(self.path, "w"), indent=1)


class ClaimSource:
    """Extracts (once) and orders the claims of a paper."""
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def claims_file(self, paper: str) -> str:
        return f"data/{self.cfg.version}/generated_claims/{paper}_{self.cfg.model}.txt"

    def ensure(self, paper: str) -> list[str]:
        f = self.claims_file(paper)
        if not os.path.exists(f):
            latex = combine_latex_sources(f"data/papers/{paper}")
            for _ in range(2):  # upstream retries forever on 0 claims; we allow one retry
                n = S.extract_claims(paper=paper, prompt=generate_claim_prompt(), model_family=self.cfg.model_family,
                                     model=self.cfg.model, claim_folder=os.path.dirname(f), latex_file=latex)
                if n:
                    break
        return format_claims(f) if os.path.exists(f) else []

    @staticmethod
    def order(paper: str, n: int) -> list[int]:
        idx = list(range(n)); random.Random(paper).shuffle(idx)  # deterministic per paper
        return idx


def process_paper(paper: str, cfg: Config, store: RunStore, source: ClaimSource,
                  runner: AttemptRunner, max_claims: int, min_errors: int) -> None:
    rec = store.paper(paper)
    if is_satisfied(rec, min_errors, max_claims):
        print(f"[{paper}] already satisfied ({count_successes(rec)} errors), skipping"); return
    calls_before = llm_calls._caller.budget.used
    claims = source.ensure(paper)
    if not claims:
        rec["final"] = "no_claims"; return
    rec["n_claims"] = len(claims)
    tried = {x["ind"] for x in rec["attempts"]}
    for ind in source.order(paper, len(claims))[:max_claims]:
        if count_successes(rec) >= min_errors:
            break
        if ind in tried:
            continue
        t0 = time.time()
        try:
            verdict = runner.run(Attempt(paper, ind, cfg))
        except Exception as e:
            traceback.print_exc()
            verdict = Verdict("exception", f"{type(e).__name__}: {e}")
        rec["attempts"].append(dict(ind=ind, status=verdict.status, detail=verdict.detail, seconds=round(time.time() - t0)))
        print(f"[{paper}] claim {ind}: {verdict.status} {verdict.detail}", flush=True)
        store.save()
        if verdict.status == "exception":  # don't burn API after an unexplained failure
            rec["final"] = "exception"; break
    if rec.get("final") != "exception":
        rec["final"] = final_label(rec, min_errors)
    rec["api_calls"] = rec.get("api_calls", 0) + llm_calls._caller.budget.used - calls_before
    store.save()


def main():
    # diagnostics: dump every thread's Python stack if a run goes quiet for 15 minutes
    faulthandler.dump_traceback_later(900, repeat=True, file=open('data/hang_stacks.log', 'a'))
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", nargs="+", required=True)
    ap.add_argument("--version", default="run1")
    ap.add_argument("--max-claims", type=int, default=DEFAULT_MAX_CLAIMS, help="max claims tried per paper (API cost cap)")
    ap.add_argument("--min-errors", type=int, default=DEFAULT_MIN_ERRORS, help="valid errors wanted per paper")
    a = ap.parse_args()
    cfg = Config(version=a.version)
    for d in ("generated_claims", "inserted_error", "filtered_error", "location_error", "identified_errors", "altered_papers"):
        os.makedirs(f"data/{cfg.version}/{d}", exist_ok=True)
    store, source, runner = RunStore(f"data/{cfg.version}/run_summary.json"), ClaimSource(cfg), AttemptRunner()
    for paper in a.papers:
        try:
            process_paper(paper, cfg, store, source, runner, a.max_claims, a.min_errors)
        except Exception as e:
            traceback.print_exc(); store.paper(paper)["final"] = f"exception: {e}"; store.save()
    print(json.dumps({k: (v.get("final"), v.get("api_calls")) for k, v in store.data.items()}, indent=1))


if __name__ == "__main__":
    main()
