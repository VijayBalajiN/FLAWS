import unittest, tempfile, os, json
import threading
from src.utils.resilient_call import RetryPolicy, Throttle, CallBudget, UsageLog, ResilientCaller, HardTimeout


def make(max_attempts=3, budget=10, sleeps=None):
    d = tempfile.mkdtemp()
    sleeps = sleeps if sleeps is not None else []
    caller = ResilientCaller(RetryPolicy(max_attempts, base_delay=1, max_delay=4, jitter=0),
                             Throttle(0, sleep=lambda s: None), CallBudget(budget),
                             UsageLog(os.path.join(d, "log.jsonl")), sleep=sleeps.append)
    return caller, os.path.join(d, "log.jsonl"), sleeps


class ResilientCallerTests(unittest.TestCase):
    def test_retries_transient_then_succeeds_with_exponential_backoff(self):
        calls = []
        def flaky(*, prompt, model, file):
            calls.append(1)
            if len(calls) < 3: raise RuntimeError("429 RESOURCE_EXHAUSTED")
            return "ok"
        caller, log, sleeps = make()
        self.assertEqual(caller.call(flaky, prompt="p", model="m"), "ok")
        self.assertEqual(sleeps, [1, 2])
        self.assertEqual(sum(1 for _ in open(log)), 3)

    def test_fatal_error_is_not_retried(self):
        caller, _, sleeps = make()
        def daily(*, prompt, model, file): raise RuntimeError("429 quota exceeded PerDay")
        with self.assertRaises(RuntimeError): caller.call(daily, prompt="p", model="m")
        self.assertEqual(sleeps, [])

    def test_empty_response_is_retried_then_raises(self):
        caller, _, sleeps = make(max_attempts=2)
        with self.assertRaises(RuntimeError): caller.call(lambda **k: "  ", prompt="p", model="m")
        self.assertEqual(len(sleeps), 1)

    def test_budget_stops_runaway(self):
        caller, _, _ = make(budget=1)
        caller.call(lambda **k: "ok", prompt="p", model="m")
        with self.assertRaises(RuntimeError): caller.call(lambda **k: "ok", prompt="p", model="m")

    def test_usage_is_logged(self):
        caller, log, _ = make()
        caller.call(lambda **k: "ok", prompt="p", model="m", usage=lambda: {"prompt_tokens": 7})
        self.assertEqual(json.loads(open(log).read())["prompt_tokens"], 7)


class HardTimeoutTests(unittest.TestCase):
    def test_returns_result_and_propagates_errors(self):
        self.assertEqual(HardTimeout(5).run(lambda: "ok"), "ok")
        with self.assertRaises(ValueError):
            HardTimeout(5).run(lambda: (_ for _ in ()).throw(ValueError("boom")))

    def test_abandons_a_blocked_call(self):
        gate = threading.Event()
        with self.assertRaises(TimeoutError):
            HardTimeout(0.05).run(gate.wait)
        gate.set()

    def test_timeout_is_retried_by_the_caller(self):
        d = tempfile.mkdtemp(); sleeps = []; gate = threading.Event(); n = []
        caller = ResilientCaller(RetryPolicy(2, 1, 1, 0), Throttle(0, sleep=lambda s: None), CallBudget(9),
                                 UsageLog(os.path.join(d, "l.jsonl")), sleep=sleeps.append, timeout=HardTimeout(0.05))
        def provider(*, prompt, model, file):
            n.append(1)
            if len(n) == 1: gate.wait()
            return "ok"
        self.assertEqual(caller.call(provider, prompt="p", model="m"), "ok")
        self.assertEqual(len(sleeps), 1)
        gate.set()


if __name__ == "__main__":
    unittest.main()
