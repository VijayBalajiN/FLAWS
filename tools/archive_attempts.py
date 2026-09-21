"""Archive the files of failed attempts so those claims can be regenerated, keeping the audit trail.

  attempt_files()     - pure-ish: which files belong to one (paper, claim) attempt
  archive_failed()    - moves them under data/<version>/_archive/<tag>/ and updates the record
Usage: python -m tools.archive_attempts --version run1 --paper arxiv_x [--tag retry1]
"""
import argparse, glob, json, os, shutil


def attempt_files(base: str, paper: str, ind: int) -> list[str]:
    patterns = [f"{base}/inserted_error/{paper}_{ind}_*", f"{base}/location_error/{paper}_{ind}_*",
                f"{base}/identified_errors/{paper}_{ind}_*", f"{base}/altered_papers/{paper}/altered_{ind}.*",
                f"{base}/altered_papers/{paper}/altered_{ind}_small.*"]
    return sorted({f for p in patterns for f in glob.glob(p)})


def archive_failed(base: str, paper: str, record: dict, tag: str) -> int:
    """Move every non-SUCCESS attempt's files into _archive/<tag>; returns how many attempts were reset."""
    keep, moved = [], []
    for a in record["attempts"]:
        (keep if a["status"] == "SUCCESS" else moved).append(a)
    for a in moved:
        for f in attempt_files(base, paper, a["ind"]):
            dest = os.path.join(base, "_archive", tag, os.path.relpath(f, base))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(f, dest)
    record["attempts"] = keep
    record.setdefault("archived", []).extend({**a, "archive_tag": tag} for a in moved)
    return len(moved)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="run1"); ap.add_argument("--paper", required=True)
    ap.add_argument("--tag", default="retry1")
    a = ap.parse_args()
    base, path = f"data/{a.version}", f"data/{a.version}/run_summary.json"
    data = json.load(open(path))
    n = archive_failed(base, a.paper, data[a.paper], a.tag)
    data[a.paper].pop("final", None)
    json.dump(data, open(path, "w"), indent=1)
    print(f"archived {n} failed attempts of {a.paper} under {base}/_archive/{a.tag}")


if __name__ == "__main__":
    main()
