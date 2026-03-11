from __future__ import annotations

import logging

import pytest

from nexus_strategy.utils.decorators import log_decision, timed


# ---------------------------------------------------------------------------
# log_decision
# ---------------------------------------------------------------------------

class TestLogDecision:
    def test_return_value_preserved(self):
        @log_decision("test_subsystem")
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_logs_info_on_call(self, caplog):
        @log_decision("MySubsystem")
        def compute(x):
            return x * 2

        with caplog.at_level(logging.INFO):
            compute(10)

        assert any("MySubsystem" in r.message for r in caplog.records)

    def test_logs_result(self, caplog):
        @log_decision("SubA")
        def greet(name):
            return f"hello {name}"

        with caplog.at_level(logging.INFO):
            result = greet("world")

        messages = " ".join(r.message for r in caplog.records)
        assert "hello world" in messages

    def test_exception_logged_at_error(self, caplog):
        @log_decision("ErrSub")
        def boom():
            raise ValueError("exploded")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError, match="exploded"):
                boom()

        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_exception_propagates(self):
        @log_decision("PropSub")
        def fail():
            raise RuntimeError("propagated")

        with pytest.raises(RuntimeError, match="propagated"):
            fail()

    def test_wraps_preserves_name(self):
        @log_decision("WrapSub")
        def my_function():
            return 1

        assert my_function.__name__ == "my_function"


# ---------------------------------------------------------------------------
# timed
# ---------------------------------------------------------------------------

class TestTimed:
    def test_return_value_preserved(self):
        @timed("my_op")
        def square(n):
            return n ** 2

        assert square(4) == 16

    def test_logs_debug_message(self, caplog):
        @timed("op_name")
        def noop():
            return None

        with caplog.at_level(logging.DEBUG):
            noop()

        assert any("op_name" in r.message for r in caplog.records)

    def test_timing_recorded(self, caplog):
        @timed("timed_op")
        def work():
            return "done"

        with caplog.at_level(logging.DEBUG):
            work()

        # At least one record should mention time (ms or s)
        messages = " ".join(r.message for r in caplog.records)
        assert any(unit in messages for unit in ["ms", "s", "sec", "elapsed", "took", "duration"])

    def test_exception_propagates(self):
        @timed("exc_op")
        def explode():
            raise KeyError("oops")

        with pytest.raises(KeyError, match="oops"):
            explode()

    def test_wraps_preserves_name(self):
        @timed("wrap_op")
        def original():
            return 0

        assert original.__name__ == "original"
