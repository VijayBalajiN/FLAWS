"""Run a callable with a hard deadline in a killable child process.

Threads cannot be killed and a CPU-bound thread keeps burning the interpreter, so work that can
run away (e.g. difflib fuzzy matching on a long paper) is forked and terminated on timeout.
The child keeps its side effects (files it writes); only a picklable result comes back.
"""
import multiprocessing as mp
from typing import Any, Callable


def _child(fn: Callable, args: tuple, kwargs: dict, queue) -> None:
    try:
        queue.put(("ok", fn(*args, **kwargs)))
    except BaseException as exc:
        queue.put(("err", f"{type(exc).__name__}: {exc}"))


def call_with_deadline(fn: Callable, seconds: float, *args: Any, **kwargs: Any) -> tuple[bool, Any]:
    """Returns (finished_in_time, result). Errors in the child are re-raised here."""
    ctx = mp.get_context("fork")
    queue = ctx.Queue()
    proc = ctx.Process(target=_child, args=(fn, args, kwargs, queue), daemon=True)
    proc.start()
    proc.join(seconds)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        if proc.is_alive():
            proc.kill()
        return False, None
    status, value = queue.get(timeout=5)
    if status == "err":
        raise RuntimeError(value)
    return True, value
