"""Evaluate all remaining errors in batches, halting on the first batch that produces an error.

  remaining()   - pure: how many valid errors still lack an evaluation result
  errored()     - pure: keys whose evaluation raised
  BatchRunner   - runs batches through an injected `run_batch` callable
Usage: python -m tools.run_eval_batches --version run1 [--batch-size 2]
"""
import argparse, json, os, subprocess, sys

from tools.run_evaluation import targets_from_summary


def remaining(summary: dict, store: dict) -> int:
    return sum(1 for t in targets_from_summary(summary) if "identified" not in store.get(f"{t.paper}#{t.ind}", {}))


def errored(store: dict) -> list[str]:
    return [k for k, r in store.items() if "error" in r]


class BatchRunner:
    def __init__(self, run_batch, read_summary, read_store):
        self.run_batch, self.read_summary, self.read_store = run_batch, read_summary, read_store

    def run(self) -> bool:
        while (left := remaining(self.read_summary(), self.read_store())) > 0:
            print(f"=== {left} left; running next batch", flush=True)
            before = self.read_store()
            self.run_batch()
            after = self.read_store()
            bad = errored(after)
            if bad:
                print(f"=== HALT: evaluation errors: {bad}", flush=True)
                return False
            if remaining(self.read_summary(), after) >= left:  # no progress -> avoid looping forever
                print("=== HALT: batch made no progress", flush=True)
                return False
        print("=== all evaluations finished", flush=True)
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="run1"); ap.add_argument("--batch-size", type=int, default=2)
    a = ap.parse_args()
    read = lambda p: (lambda: json.load(open(p)) if os.path.exists(p) else {})
    run = lambda: subprocess.run([sys.executable, "-W", "ignore", "-m", "tools.run_evaluation", "--version", a.version,
                                  "--limit", str(a.batch_size)])
    ok = BatchRunner(run, read(f"data/{a.version}/run_summary.json"), read(f"data/{a.version}/evaluation_summary.json")).run()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
