"""Resilience around LLM calls, split by responsibility (SRP) and composed by injection (DIP).

    RetryPolicy  - decides *whether* to retry and *how long* to wait
    Throttle     - spaces calls out in time
    CallBudget   - hard cap on total calls
    UsageLog     - append-only JSONL record of every attempt
    ResilientCaller - composes the four around any provider callable

None of them knows about a specific provider; providers are plugged in as plain callables,
so adding a provider or swapping a policy never requires editing these classes (OCP).
"""
import json
import os
import random
import threading
import time
from typing import Callable, Protocol


class RetryPolicy:
    """Classifies errors as transient/fatal and produces exponential backoff with jitter."""

    TRANSIENT = (
        "429", "500", "502", "503", "504", "resource_exhausted", "resourceexhausted",
        "unavailable", "deadline", "timeout", "timed out", "overloaded", "rate limit",
        "rate_limit", "connection", "temporarily", "internal error", "empty response",
    )
    FATAL = ("perday", "per day", "daily", "api key not valid", "permission_denied",
             "invalid_argument", "billing")

    def __init__(self, max_attempts: int = 6, base_delay: float = 20.0,
                 max_delay: float = 300.0, jitter: float = 5.0):
        self.max_attempts, self.base_delay = max_attempts, base_delay
        self.max_delay, self.jitter = max_delay, jitter

    def is_retryable(self, exc: Exception) -> bool:
        msg = f"{type(exc).__name__} {exc}".lower()
        if any(f in msg for f in self.FATAL):
            return False
        return any(t in msg for t in self.TRANSIENT)

    def delay(self, attempt: int) -> float:
        return min(self.base_delay * 2 ** (attempt - 1), self.max_delay) + random.uniform(0, self.jitter)


class Throttle:
    """Guarantees a minimum gap between consecutive calls."""

    def __init__(self, min_interval: float, clock=time.time, sleep=time.sleep):
        self.min_interval, self._clock, self._sleep = min_interval, clock, sleep
        self._last = 0.0

    def wait(self) -> None:
        gap = self.min_interval - (self._clock() - self._last)
        if gap > 0:
            self._sleep(gap)
        self._last = self._clock()


class CallBudget:
    """Fails loudly once the total number of attempts reaches the cap."""

    def __init__(self, max_calls: int):
        self.max_calls, self.used = max_calls, 0

    def consume(self) -> None:
        if self.used >= self.max_calls:
            raise RuntimeError(f"API call budget of {self.max_calls} exhausted, stopping")
        self.used += 1


class UsageLog:
    """Append-only JSONL audit trail of every attempt (success or failure)."""

    def __init__(self, path: str):
        self.path = path

    def record(self, **fields) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(fields) + "\n")


class HardTimeout:
    """Wall-clock limit for one call. Some client libraries (e.g. gRPC) can block forever and
    ignore their own timeouts; the call runs on a daemon thread we can abandon. The raised
    TimeoutError is classed as transient by RetryPolicy, so the call is retried."""

    def __init__(self, seconds: float | None):
        self.seconds = seconds

    def run(self, fn: Callable[[], str]) -> str:
        if not self.seconds:
            return fn()
        box: dict = {}

        def target():
            try:
                box["out"] = fn()
            except BaseException as exc:  # re-raised on the caller's thread
                box["exc"] = exc

        worker = threading.Thread(target=target, daemon=True)
        worker.start()
        worker.join(self.seconds)
        if worker.is_alive():
            raise TimeoutError(f"call timed out after {self.seconds:.0f}s (abandoned)")
        if "exc" in box:
            raise box["exc"]
        return box["out"]


class Provider(Protocol):
    def __call__(self, *, prompt: str, model: str, file: str | None) -> str: ...


class ResilientCaller:
    """Runs a provider call under throttle + budget + retry, logging each attempt."""

    def __init__(self, policy: RetryPolicy, throttle: Throttle, budget: CallBudget,
                 log: UsageLog, sleep: Callable[[float], None] = time.sleep,
                 timeout: HardTimeout | None = None):
        self.policy, self.throttle, self.budget, self.log, self._sleep = policy, throttle, budget, log, sleep
        self.timeout = timeout or HardTimeout(None)

    def call(self, provider: Provider, *, prompt: str, model: str, file: str | None = None,
             usage: Callable[[], dict] = dict) -> str:
        for attempt in range(1, self.policy.max_attempts + 1):
            self.budget.consume()
            self.throttle.wait()
            started = time.time()
            base = dict(ts=started, model=model, attempt=attempt, prompt_chars=len(prompt))
            try:
                out = self.timeout.run(lambda: provider(prompt=prompt, model=model, file=file))
                if out is None or not str(out).strip():
                    raise RuntimeError("empty response")
                self.log.record(**base, ok=True, seconds=round(time.time() - started, 1),
                                output_chars=len(out), **usage())
                return out
            except Exception as exc:
                retryable = self.policy.is_retryable(exc)
                self.log.record(**base, ok=False, seconds=round(time.time() - started, 1),
                                error=f"{type(exc).__name__}: {str(exc)[:300]}", retryable=retryable)
                if not retryable or attempt == self.policy.max_attempts:
                    raise
                wait = self.policy.delay(attempt)
                print(f"[llm] attempt {attempt}/{self.policy.max_attempts} failed "
                      f"({type(exc).__name__}); retrying in {wait:.0f}s")
                self._sleep(wait)
        raise AssertionError("unreachable")
