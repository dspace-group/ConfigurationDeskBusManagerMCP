"""Single-Apartment-Thread (STA) gateway for all COM calls.

Rules (non-negotiable):
- All COM objects MUST be created and used on the STA thread only.
- Never await inside the STA thread body.
- pythoncom.PumpWaitingMessages() is called between queue items.
- CoInitialize / CoUninitialize bracket the thread body.
"""

from __future__ import annotations

import concurrent.futures
import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

_log = logging.getLogger(__name__)

_QUEUE_POLL_INTERVAL: float = 0.05


@dataclass
class _Task:
    """Work item submitted to the STA thread."""

    fn: Callable[..., Any]
    args: tuple[Any, ...]
    future: concurrent.futures.Future[Any] = field(default_factory=concurrent.futures.Future)


class STAThread:
    """Dedicated Windows STA thread that owns all COM objects."""

    def __init__(self) -> None:
        self._queue: queue.Queue[_Task | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="sta-com", daemon=False)

    def start(self) -> None:
        self._thread.start()
        _log.info("STA thread started (tid=%s)", self._thread.ident)

    def stop(self, timeout: float = 5.0) -> None:
        self._queue.put(None)
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            _log.warning("STA thread did not stop within %.1f s", timeout)
        else:
            _log.info("STA thread stopped")

    def submit(self, fn: Callable[..., Any], *args: Any) -> concurrent.futures.Future[Any]:
        task = _Task(fn=fn, args=args)
        self._queue.put(task)
        return task.future

    def _run(self) -> None:
        pythoncom = self._co_initialize()
        _log.debug("STA thread: message pump running")
        try:
            while True:
                self._pump(pythoncom)
                try:
                    task = self._queue.get(timeout=_QUEUE_POLL_INTERVAL)
                except queue.Empty:
                    continue

                if task is None:
                    break

                try:
                    result = task.fn(*task.args)
                    try:
                        task.future.set_result(result)
                    except concurrent.futures.InvalidStateError:
                        _log.debug("STA: discarding result for cancelled future (%s)", task.fn)
                except Exception as exc:  # noqa: BLE001
                    try:
                        task.future.set_exception(exc)
                    except concurrent.futures.InvalidStateError:
                        _log.debug(
                            "STA: discarding exception for cancelled future (%s): %s",
                            task.fn,
                            exc,
                        )
        finally:
            self._co_uninitialize(pythoncom)

    @staticmethod
    def _co_initialize() -> Any:
        try:
            import pythoncom  # noqa: PLC0415

            pythoncom.CoInitialize()
            _log.debug("STA thread: CoInitialize OK")
            return pythoncom
        except ImportError:
            _log.warning("pythoncom not available — COM calls will fail on this platform")
            return None

    @staticmethod
    def _co_uninitialize(pythoncom: Any) -> None:
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
                _log.debug("STA thread: CoUninitialize OK")
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _pump(pythoncom: Any) -> None:
        if pythoncom is not None:
            try:
                pythoncom.PumpWaitingMessages()
            except Exception:  # noqa: BLE001
                pass


# ── Module-level singleton ─────────────────────────────────────────────────────

_sta_thread: STAThread | None = None


def get_sta_thread() -> STAThread:
    if _sta_thread is None:
        msg = "STA thread not started. Call startup() first."
        raise RuntimeError(msg)
    return _sta_thread


def startup() -> None:
    global _sta_thread  # noqa: PLW0603
    if _sta_thread is None:
        _sta_thread = STAThread()
        _sta_thread.start()


def shutdown() -> None:
    global _sta_thread  # noqa: PLW0603
    if _sta_thread is not None:
        _sta_thread.stop()
        _sta_thread = None
