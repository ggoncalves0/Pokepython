"""Testes do executor de tarefas em segundo plano (pokedex/background.py).

Sem Tk: o agendador do after() é falso e roda as chamadas na mão.
"""

import threading
import time
import unittest
from collections.abc import Callable
from typing import Any

from pokedex.background import TaskRunner


class FakeScheduler:
    """Faz o papel do root.after(): guarda as chamadas para rodar depois."""

    def __init__(self) -> None:
        self.pending: list[Callable[[], None]] = []

    def __call__(self, _delay_ms: int, callback: Callable[[], None]) -> None:
        self.pending.append(callback)

    def run_until(self, done: Callable[[], bool], timeout: float = 5) -> None:
        limit = time.monotonic() + timeout
        while not done():
            if time.monotonic() > limit:
                raise AssertionError("tempo esgotado")
            calls, self.pending = self.pending, []
            for call in calls:
                call()
            time.sleep(0.005)


class TaskRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schedule = FakeScheduler()
        self.results: list[Any] = []

    def test_result_comes_back_through_scheduler(self) -> None:
        runner = TaskRunner(self.schedule, workers=1, name="teste")
        runner.submit(lambda: 6 * 7, self.results.append)
        self.assertEqual(self.results, [])  # nunca na thread de trabalho
        self.schedule.run_until(lambda: bool(self.results))
        self.assertEqual(self.results, [42])

    def test_errors_go_to_on_error(self) -> None:
        runner = TaskRunner(self.schedule, workers=1, name="teste")
        errors: list[Exception] = []

        def fail() -> None:
            raise KeyError("sem tipo")

        runner.submit(fail, self.results.append, on_error=errors.append)
        self.schedule.run_until(lambda: bool(errors))
        self.assertIsInstance(errors[0], KeyError)
        self.assertEqual(self.results, [])

    def test_errors_without_handler_are_logged(self) -> None:
        runner = TaskRunner(self.schedule, workers=1, name="teste")

        def fail() -> None:
            raise RuntimeError("inesperado")

        with self.assertLogs("pokedex.background", level="ERROR"):
            runner.submit(fail, self.results.append)
            self.schedule.run_until(lambda: runner.idle)

    def test_cancelled_task_does_not_call_back(self) -> None:
        runner = TaskRunner(self.schedule, workers=1, name="teste")
        gate = threading.Event()
        runner.submit(gate.wait, lambda _: None)  # ocupa a única thread
        ticket = runner.submit(lambda: "velho", self.results.append)
        ticket.cancel()
        gate.set()
        self.schedule.run_until(lambda: runner.idle)
        self.assertEqual(self.results, [])

    def test_lower_priority_number_runs_first(self) -> None:
        runner = TaskRunner(self.schedule, workers=1, name="teste")
        gate = threading.Event()
        runner.submit(gate.wait, lambda _: None)  # ocupa a única thread
        runner.submit(lambda: "pré-carga", self.results.append, priority=2)
        runner.submit(lambda: "clique", self.results.append, priority=0)
        gate.set()
        self.schedule.run_until(lambda: len(self.results) == 2)
        self.assertEqual(self.results, ["clique", "pré-carga"])

    def test_deliver_ready_does_not_wait_for_next_poll(self) -> None:
        # O card de espera usa isto: o que já chegou entra na hora.
        runner = TaskRunner(self.schedule, workers=1, name="teste")
        runner.submit(lambda: "pronto", self.results.append)
        limit = time.monotonic() + 5
        while not self.results and time.monotonic() < limit:
            runner.deliver_ready()  # sem rodar o agendador
            time.sleep(0.005)
        self.assertEqual(self.results, ["pronto"])
        self.assertTrue(runner.idle)

    def test_stops_polling_when_idle(self) -> None:
        runner = TaskRunner(self.schedule, workers=2, name="teste")
        runner.submit(lambda: 1, self.results.append)
        self.schedule.run_until(lambda: runner.idle)
        self.schedule.run_until(lambda: not self.schedule.pending)
        self.assertEqual(self.schedule.pending, [])


if __name__ == "__main__":
    unittest.main()
