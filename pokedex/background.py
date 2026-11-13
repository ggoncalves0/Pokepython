"""Tarefas em segundo plano, com o resultado entregue na thread do Tk.

Só a thread principal pode mexer em widgets (o Tkinter não é
thread-safe). As tarefas rodam em threads de trabalho; o resultado volta
por uma fila, que a thread principal esvazia com after(), só enquanto há
tarefas pendentes.

As threads são daemon: fechar a janela não espera downloads em andamento.
"""

import itertools
import logging
import queue
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

POLL_MS = 10  # intervalo para conferir resultados, só com tarefas pendentes

Schedule = Callable[[int, Callable[[], None]], Any]  # como root.after


class Ticket:
    """Permite cancelar uma tarefa: se ainda não começou, nem roda; se já
    começou, o resultado é descartado."""

    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class _Task:
    def __init__(
        self,
        ticket: Ticket,
        task: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None] | None,
    ) -> None:
        self.ticket = ticket
        self.task = task
        self.on_success = on_success
        self.on_error = on_error
        self.result: Any = None
        self.error: Exception | None = None


class TaskRunner:
    """Executa tarefas em `workers` threads, por ordem de prioridade.

    Prioridade menor roda antes (0 para o que o usuário pediu agora).
    """

    def __init__(self, schedule: Schedule, workers: int, name: str) -> None:
        self._schedule = schedule
        self._tasks: queue.PriorityQueue[tuple[int, int, _Task]] = (
            queue.PriorityQueue()
        )
        self._done: queue.SimpleQueue[_Task] = queue.SimpleQueue()
        self._order = itertools.count()  # desempate: ordem de chegada
        self._outstanding = 0  # só a thread principal mexe neste número
        self._polling = False
        self._closed = False
        for index in range(workers):
            threading.Thread(
                target=self._work, name=f"{name}-{index}", daemon=True
            ).start()

    @property
    def idle(self) -> bool:
        """Nenhuma tarefa pendente (inclusive resultados por entregar)."""
        return self._outstanding == 0

    def submit(
        self,
        task: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None] | None = None,
        priority: int = 1,
    ) -> Ticket:
        """Agenda `task`; o resultado vai para `on_success` na thread do Tk.

        Sem `on_error`, um erro é registrado no log.
        """
        ticket = Ticket()
        self._outstanding += 1
        item = _Task(ticket, task, on_success, on_error)
        self._tasks.put((priority, next(self._order), item))
        self._start_polling()
        return ticket

    def close(self) -> None:
        """Para de entregar resultados (a janela vai fechar)."""
        self._closed = True

    def deliver_ready(self) -> None:
        """Entrega agora os resultados que já chegaram, sem esperar a
        próxima conferência. Só na thread do Tk."""
        if self._closed:
            return
        while True:
            try:
                item = self._done.get_nowait()
            except queue.Empty:
                return
            self._outstanding -= 1
            if not item.ticket.cancelled:
                self._deliver(item)

    def _work(self) -> None:
        while True:
            _, _, item = self._tasks.get()
            if not item.ticket.cancelled and not self._closed:
                try:
                    item.result = item.task()
                # Qualquer erro vai para a thread do Tk (on_error ou log).
                except Exception as error:  # noqa: BLE001
                    item.error = error
            self._done.put(item)

    def _start_polling(self) -> None:
        if not self._polling and not self._closed:
            self._polling = True
            self._schedule(POLL_MS, self._poll)

    def _poll(self) -> None:
        self._polling = False
        self.deliver_ready()
        if self._outstanding:
            self._start_polling()

    @staticmethod
    def _deliver(item: _Task) -> None:
        try:
            if item.error is None:
                item.on_success(item.result)
            elif item.on_error is not None:
                item.on_error(item.error)
            else:
                logger.error(
                    "Tarefa em segundo plano falhou.", exc_info=item.error
                )
        except Exception:
            # Um erro ao mostrar o resultado não pode parar as outras
            # entregas.
            logger.exception("Erro ao tratar o resultado de uma tarefa.")
