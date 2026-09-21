"""Run accepted papers through run_flaws_set two at a time, halting on the first real problem.

  chunk()           - pure: split a list into sets
  problems()        - pure: which attempt statuses count as "stop and fix" (vs. normal attrition)
  SetSequencer      - runs sets in order through an injected `run_set` callable
Usage: python -m tools.run_sets --version run1 [--set-size 2] [--max-claims 7] [--min-errors 2]
"""
import argparse, json, os, subprocess, sys

from tools.run_policy import DEFAULT_MAX_CLAIMS, DEFAULT_MIN_ERRORS, is_satisfied

PROBLEM_STATUSES = {"exception", "compile_failed", "unresolved_refs"}


def chunk(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def problems(record: dict) -> list[str]:
    """Attempt statuses that indicate a pipeline/tooling fault rather than a filtered-out error."""
    found = [a["status"] for a in record.get("attempts", []) if a["status"] in PROBLEM_STATUSES]
    if str(record.get("final", "")).startswith("exception"):
        found.append(record["final"])
    return found


class SetSequencer:
    def __init__(self, run_set, read_summary, max_claims: int, min_errors: int):
        self.run_set, self.read_summary = run_set, read_summary
        self.max_claims, self.min_errors = max_claims, min_errors

    def run(self, sets: list[list[str]]) -> bool:
        for i, papers in enumerate(sets, 1):
            done = {p for p, r in self.read_summary().items() if is_satisfied(r, self.min_errors, self.max_claims)}
            todo = [p for p in papers if p not in done]
            if not todo:
                continue
            print(f"=== set {i}/{len(sets)}: {todo}", flush=True)
            self.run_set(todo)
            summary = self.read_summary()
            bad = {p: problems(summary.get(p, {})) for p in todo if problems(summary.get(p, {}))}
            if bad:
                print(f"=== HALT: problems in set {i}: {bad}", flush=True)
                return False
        print("=== all sets finished", flush=True)
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="run1")
    ap.add_argument("--set-size", type=int, default=2)
    ap.add_argument("--max-claims", type=int, default=DEFAULT_MAX_CLAIMS, help="claims tried per paper")
    ap.add_argument("--min-errors", type=int, default=DEFAULT_MIN_ERRORS, help="valid errors wanted per paper")
    a = ap.parse_args()
    state = json.load(open("tools/preflight_state.json"))
    papers = [v["folder"] for v in state.values() if v["status"] == "ACCEPT"]
    summary_path = f"data/{a.version}/run_summary.json"
    read = lambda: json.load(open(summary_path)) if os.path.exists(summary_path) else {}
    run = lambda ps: subprocess.run([sys.executable, "-W", "ignore", "-m", "tools.run_flaws_set", "--papers", *ps,
                                     "--version", a.version, "--max-claims", str(a.max_claims), "--min-errors", str(a.min_errors)])
    sys.exit(0 if SetSequencer(run, read, a.max_claims, a.min_errors).run(chunk(papers, a.set_size)) else 1)


if __name__ == "__main__":
    main()
