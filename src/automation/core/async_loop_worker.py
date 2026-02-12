# src/automation/core/async_loop_worker.py
import asyncio
import logging
import threading
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

class AsyncLoopWorker:
    """Külön szálon futó asyncio event loop."""
    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive(): return
        def _target():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._running.set()
            try:
                self._loop.run_forever()
            finally:
                pending = asyncio.all_tasks(loop=self._loop)
                if pending:
                    for t in pending: t.cancel()
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                try:
                    self._loop.run_until_complete(self._loop.shutdown_asyncgens())
                except Exception as e:
                    logger.exception("Hiba az async generátorok leállításakor: %s", e)
                self._loop.close()
        self._thread = threading.Thread(target=_target, name="AsyncLoopWorkerThread", daemon=True)
        self._thread.start()
        if not self._running.wait(timeout=5):
            raise RuntimeError("AsyncLoopWorker: Nem sikerült elindítani az event loop-ot.")

    def request_stop(self) -> None:
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def stop(self, timeout: float = 5.0) -> None:
        if not (self._thread and self._thread.is_alive()): return
        self.request_stop()
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            logger.warning("AsyncLoopWorker: a worker szál nem állt le %s másodpercen belül.", timeout)

    def run_coro_threadsafe(self, coro: Awaitable, *, callback: Optional[Callable[[asyncio.Future], None]] = None) -> asyncio.Future:
        if not (self._loop and self.is_running):
            future = asyncio.Future()
            future.set_exception(RuntimeError("AsyncLoopWorker: event loop nem fut."))
            return future
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        if callback: fut.add_done_callback(callback)
        return fut

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())