"""uninv backend package.

`main()` is the console entry point declared in pyproject.toml, so
`uv run uninv-backend` starts the API server.
"""

import argparse

__version__ = "1.2.0"


def is_parent_alive(parent_pid: int) -> bool:
    """Check if the parent process with PID parent_pid is still running."""
    import sys

    if sys.platform == "win32":
        import ctypes

        synchronize = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, parent_pid)
        if not handle:
            return False
        res = ctypes.windll.kernel32.WaitForSingleObject(handle, 0)
        ctypes.windll.kernel32.CloseHandle(handle)
        # 0x102 is WAIT_TIMEOUT, indicating the process is still actively running.
        return res == 0x00000102
    else:
        import os

        try:
            os.kill(parent_pid, 0)
            return True
        except OSError:
            return False


def start_parent_watchdog(parent_pid: int, poll_interval: float = 1.0) -> None:
    """Start a background daemon thread that terminates uninv-backend if parent process dies."""
    import logging
    import os
    import threading
    import time

    logger = logging.getLogger("uninv_backend.watchdog")

    def _watch() -> None:
        logger.info("Parent watchdog active: monitoring parent PID %d", parent_pid)
        while True:
            time.sleep(poll_interval)
            if not is_parent_alive(parent_pid):
                logger.info(
                    "Parent process %d terminated. Shutting down uninv-backend automatically.",
                    parent_pid,
                )
                os._exit(0)

    thread = threading.Thread(target=_watch, daemon=True, name="parent-watchdog")
    thread.start()


def main() -> None:
    """Start the FastAPI server with uvicorn."""
    import uvicorn

    from uninv_backend.config import get_settings

    settings = get_settings()

    parser = argparse.ArgumentParser(prog="uninv-backend", description="Run the uninv API server.")
    parser.add_argument(
        "--host", default=settings.host, help="interface to bind (default: %(default)s)"
    )
    parser.add_argument(
        "--port", type=int, default=settings.port, help="port (default: %(default)s)"
    )
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes (dev)")
    parser.add_argument(
        "--parent-pid",
        type=int,
        default=None,
        help="parent process ID to monitor; automatically exit if parent dies",
    )
    args = parser.parse_args()

    if args.parent_pid:
        start_parent_watchdog(args.parent_pid)

    if args.reload:
        uvicorn.run(
            "uninv_backend.app:app",
            host=args.host,
            port=args.port,
            reload=True,
        )
    else:
        from uninv_backend.app import app

        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
        )
