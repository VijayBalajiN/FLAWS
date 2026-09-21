"""External identification + evaluation of the inserted errors, through FLAWS's own
`identify_and_evaluate` (unchanged): a model reads the altered PDF and lists suspected error
excerpts; success = matched by Levenshtein similarity OR by an LLM judge.

  targets_from_summary()  - pure: the (paper, claim) pairs that hold a valid inserted error
  read_verdicts()         - reads the per-metric verdicts FLAWS wrote to disk
  EvalStore               - the only writer of evaluation_summary.json
  Evaluator               - runs one target through an injected identify function
Usage: python -m tools.run_evaluation --version run1 [--limit 2] [--model gemini-2.5-pro]
"""
import argparse, json, os, sys, traceback
from dataclasses import dataclass

sys.path.insert(0, os.getcwd())


@dataclass(frozen=True)
class Target:
    paper: str
    ind: int


@dataclass(frozen=True)
class Verdict:
    identified: bool
    by_levenshtein: bool
    by_llm_judge: bool


def targets_from_summary(summary: dict) -> list[Target]:
    return [Target(p, a["ind"]) for p, rec in summary.items()
            for a in rec["attempts"] if a["status"] == "SUCCESS"]


def read_verdicts(folder: str, model: str, target: Target, top_k: int, threshold: float,
                  parse_lev, parse_judge) -> Verdict:
    base = f"{folder}/{target.paper}_{target.ind}_{model}"
    lev = bool(parse_lev(open(f"{base}_score.txt").read(), top_k, threshold=threshold))
    judge = bool(parse_judge(open(f"{base}_comparison.txt").read(), top_k))
    return Verdict(lev or judge, lev, judge)


class EvalStore:
    def __init__(self, path: str):
        self.path = path
        self.data = json.load(open(path)) if os.path.exists(path) else {}

    @staticmethod
    def key(t: Target) -> str:
        return f"{t.paper}#{t.ind}"

    def done(self, t: Target) -> bool:
        return self.key(t) in self.data and "identified" in self.data[self.key(t)]

    def put(self, t: Target, record: dict) -> None:
        self.data[self.key(t)] = record
        json.dump(self.data, open(self.path, "w"), indent=1)


class Evaluator:
    def __init__(self, identify, read, store: EvalStore):
        self.identify, self.read, self.store = identify, read, store

    def run(self, t: Target) -> None:
        if self.store.done(t):
            return
        try:
            self.identify(t)
            v = self.read(t)
            self.store.put(t, dict(identified=v.identified, by_levenshtein=v.by_levenshtein, by_llm_judge=v.by_llm_judge))
        except Exception as e:
            traceback.print_exc()
            self.store.put(t, dict(error=f"{type(e).__name__}: {e}"))


def main():
    from src.pipeline.single_process.single_error_identification import identify_and_evaluate
    from src.utils.evaluation_helpers import parse_levenshtein, parse_llm_as_a_judge

    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="run1")
    ap.add_argument("--model", default="gemini-2.5-pro")
    ap.add_argument("--family", default="gemini")
    ap.add_argument("--limit", type=int, default=None, help="evaluate at most N not-yet-done errors")
    a = ap.parse_args()
    v, model, top_k, thr = a.version, a.model, 10, 0.5
    folder = f"data/{v}/evaluation_errors"
    os.makedirs(folder, exist_ok=True)
    summary = json.load(open(f"data/{v}/run_summary.json"))
    store = EvalStore(f"data/{v}/evaluation_summary.json")

    def identify(t: Target):
        identify_and_evaluate(
            model_insertion="gemini-2.5-pro", model_family_insertion="gemini",   # names the inserted-error files + the judge
            model_identification=model, model_family_identification=a.family,
            error_folder=f"data/{v}/inserted_error", location_folder=f"data/{v}/location_error",
            external_identify_folder=folder, version_control=v, paper=t.paper, ind=t.ind,
            rerun_external_identification=False, rerun_evaluation=False,
            levenshtein_threshold=thr, top_k=top_k)

    read = lambda t: read_verdicts(folder, model, t, top_k, thr, parse_levenshtein, parse_llm_as_a_judge)
    ev = Evaluator(identify, read, store)
    todo = [t for t in targets_from_summary(summary) if not store.done(t)]
    for t in todo[: a.limit]:
        ev.run(t)
        print(f"[{t.paper} #{t.ind}] {store.data[store.key(t)]}", flush=True)
    done = [r for r in store.data.values() if "identified" in r]
    print(f"evaluated {len(done)}/{len(targets_from_summary(summary))}; identified {sum(r['identified'] for r in done)}")


if __name__ == "__main__":
    main()
