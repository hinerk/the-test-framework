from __future__ import annotations

import threading
import time
from contextlib import contextmanager

from dataclasses import dataclass
from logging import getLogger
from multiprocessing import Process
from threading import Thread
from typing import Callable, Any

logger = getLogger(__name__)


@dataclass
class MonitorError:
    origin: str
    message: str
    exception: Exception | None = None


class TestSystemMonitor:
    def __init__(self):
        self._callbacks = {}
        self._tasks = []
        self._monitor_is_running = False
        self._error: list[MonitorError] = []

    def set_error(self, origin: str, message: str, exception: Exception | None = None) -> None:
        logger.exception(f"{origin!r} reports {message!r} ({exception!r})", exc_info=exception)
        self._error.append(MonitorError(origin, message, exception))

    @property
    def wrecked(self) -> bool:
        return len(self._error) > 0

    @property
    def errors(self):
        return self._error

    def add_monitor_callback(self, callback: Callable[[], bool], on_error_callback: Callable[[], Any] | None = None) -> None:
        """
        Add a monitor callback which asserts the system's state.
        :param callback:
        :param on_error_callback: a callback which is executed when callback returns False.
        :return:
        """
        self._callbacks[callback] = on_error_callback

    def remove_monitor_callback(self, callback: Callable[[], bool]):
        self._callbacks.pop(callback)

    def add_task(self, task: Thread | Process):
        logger.debug(f"adding task {task.name}")
        self._tasks.append(task)

    def remove_task(self, task: Thread | Process):
        logger.debug(f"Removing task {task.name}")
        self._tasks.remove(task)

    @contextmanager
    def task(self,  task: Thread | Process):
        self.add_task(task)
        yield
        self.remove_task(task)

    @contextmanager
    def monitor(self, callback: Callable[[], bool], on_error_callback: Callable[[], Any]):
        self.add_monitor_callback(callback, on_error_callback)
        yield
        self.remove_monitor_callback(callback)

    def quit(self):
        self._monitor_is_running = False

    def monitor_loop(self):
        self._monitor_is_running = True
        while self._monitor_is_running:
            time.sleep(1)
            for callback, on_error_callback in self._callbacks.items():
                if not callback():
                    logger.critical("shit hit the fan!")
                    if on_error_callback is not None:
                        on_error_callback()
            for task in self._tasks:
                if isinstance(task, Process):
                    name = task.name
                    pid = task.pid
                    if task.is_alive():
                        logger.log(0, f"Process {name} (PID: {pid}) seem to be alive!")
                    else:
                        exit_code = task.exitcode
                        self.set_error(threading.current_thread().name, f"{name} (PID: {pid}) seem to be dead! (exit code: {exit_code})")
                else:
                    if task.is_alive():
                        logger.log(0, f"Task {task.name!r} seem to be alive!")
                    else:
                        self.set_error(threading.current_thread().name, f"{task.name} seem to be dead!")
