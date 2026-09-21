"""Stopping policy for a paper, as pure functions (no I/O), shared by the driver and the sequencer.

A paper is *satisfied* when it has enough valid errors, or nothing more can be tried.
"""

DEFAULT_MAX_CLAIMS = 7   # claims tried per paper before giving up (upstream has no cap)
DEFAULT_MIN_ERRORS = 2   # valid, compiled errors wanted per paper


def count_successes(record: dict) -> int:
    return sum(1 for a in record.get("attempts", []) if a["status"] == "SUCCESS")


def budget_exhausted(record: dict, max_claims: int) -> bool:
    n = record.get("n_claims")
    return bool(n) and len(record.get("attempts", [])) >= min(n, max_claims)


def is_satisfied(record: dict, min_errors: int, max_claims: int) -> bool:
    if record.get("final") == "no_claims":
        return True
    return count_successes(record) >= min_errors or budget_exhausted(record, max_claims)


def final_label(record: dict, min_errors: int) -> str:
    got = count_successes(record)
    if got >= min_errors:
        return "SUCCESS"
    return "PARTIAL" if got else "no_valid_error_within_budget"
