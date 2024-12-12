"""Management script for running the application with auto-reload in development."""

import asyncio
import logging
import multiprocessing
import os
import signal
import sys
import threading
import time
from pathlib import Path
from types import FrameType

# Configure debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("jeeves")

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

SUBPROCESS_CHECK_INTERVAL = 0.1  # How often to check if subprocess is alive (seconds)
SUBPROCESS_TERMINATE_TIMEOUT = 2  # How long to wait for graceful termination (seconds)
SUBPROCESS_KILL_TIMEOUT = 1  # How long to wait after force kill (seconds)


def print_notification(message: str) -> None:
    """Print a visible notification."""
    width = 80
    print("\n" + "!" * width)
    print(message.center(width))
    print("!" * width + "\n")


def run_app() -> None:
    """Run the application in a subprocess."""
    try:
        logger.debug("Starting application in subprocess")
        from jeeves.scripts.ui.jeeves import JeevesUI

        async def run():
            logger.debug("Initializing JeevesUI")
            ui = JeevesUI()
            await ui.run()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logger.debug("Running event loop")
            loop.run_until_complete(run())
        except SystemExit:
            logger.debug("SystemExit received in run_app")
        finally:
            try:
                logger.debug("Cleaning up event loop")
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
            except Exception as e:
                logger.error(f"Error during loop cleanup: {e}")
            logger.debug("Event loop closed")

    except KeyboardInterrupt:
        logger.debug("KeyboardInterrupt received in run_app")
    except SystemExit:
        logger.debug("SystemExit received in run_app")
    except Exception as e:
        logger.error(f"Unexpected error in run_app: {e}", exc_info=True)
    finally:
        logger.debug("run_app completed")


class Reloader:
    """Handles code reloading by running the app in a subprocess."""

    def __init__(self, debug: bool = False) -> None:
        """Initialize the reloader.

        Args:
            debug: Whether to run in debug mode
        """
        self.debug = debug
        self.should_exit = threading.Event()
        self.pid = os.getpid()
        self.process = None
        self.mtimes = {}
        self.last_reload = 0

    def signal_handler(self, sig: int, frame: FrameType | None) -> None:
        """Handle termination signals."""
        self.should_exit.set()

    def run(self) -> None:
        """Run the reloader process."""
        self.startup()

        while not self.should_exit.is_set():
            # Check if subprocess has terminated
            if self.process and not self.process.is_alive():
                logger.debug("Subprocess has terminated, initiating shutdown")
                self.should_exit.set()
                break

            if self.should_restart():
                print_notification("Code changes detected! Reloading application...")
                self.restart()

            # Check for process termination
            self.should_exit.wait(SUBPROCESS_CHECK_INTERVAL)

        self.shutdown()

    def should_restart(self) -> bool:
        """Check if any Python files have been modified."""
        current_time = time.time()
        if current_time - self.last_reload < 1:  # Debounce reloads
            return False

        for file in self.iter_py_files():
            try:
                mtime = file.stat().st_mtime
            except OSError:
                continue

            old_time = self.mtimes.get(file)
            if old_time is None:
                self.mtimes[file] = mtime
                continue
            elif mtime > old_time:
                rel_path = file.relative_to(Path(__file__).parent.parent)
                print_notification(f"Modified file: {rel_path}")
                self.mtimes = {}  # Reset all mtimes
                self.last_reload = current_time
                return True
        return False

    def iter_py_files(self):
        """Iterate over all Python files in the project."""
        root_dir = Path(__file__).parent.parent
        yield from (path.resolve() for path in root_dir.rglob("*.py"))

    def startup(self) -> None:
        """Start the initial subprocess."""
        print_notification(f"Starting Jeeves with auto-reload (PID: {self.pid})")

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.signal_handler)

        self.process = self.get_subprocess()
        self.process.start()

    def restart(self) -> None:
        """Restart the subprocess."""
        self._terminate_process()
        self.process = self.get_subprocess()
        self.process.start()

    def shutdown(self) -> None:
        """Shutdown the reloader."""
        self._terminate_process()
        print_notification("Stopping Jeeves")
        sys.exit(0)

    def _terminate_process(self) -> None:
        """Terminate the subprocess with timeout."""
        if not self.process:
            return

        try:
            if self.process.is_alive():
                logger.debug("Terminating subprocess")
                self.process.terminate()
                self.process.join(timeout=SUBPROCESS_TERMINATE_TIMEOUT)

                if self.process.is_alive():
                    logger.warning("Process did not terminate gracefully, forcing kill")
                    self.process.kill()
                    self.process.join(timeout=SUBPROCESS_KILL_TIMEOUT)
        except Exception as e:
            logger.error(f"Error during process termination: {e}")

    def get_subprocess(self) -> multiprocessing.Process:
        """Create a subprocess to run the application."""
        if sys.platform == "win32":
            # Windows needs a different process start method
            multiprocessing.set_start_method("spawn", force=True)

        return multiprocessing.Process(target=run_app)


def main() -> None:
    """Run the application."""
    import argparse

    parser = argparse.ArgumentParser(description="Run the Jeeves application server.")
    parser.add_argument(
        "--debug", action="store_true", help="Run in debug mode with auto-reload"
    )
    args = parser.parse_args()

    try:
        if args.debug:
            reloader = Reloader(debug=True)
            reloader.run()
        else:
            # In non-debug mode, run the app directly
            run_app()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        print("Goodbye!")


if __name__ == "__main__":
    main()
