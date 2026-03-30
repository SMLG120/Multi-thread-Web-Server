"""
utils/logger.py — Request/Response Logger

Thread-safe logger that appends one line per HTTP transaction to a log file.

Log format (fixed-width columns):
    TIMESTAMP            CLIENT-IP     PATH                      STATUS       
    2026-04-10 14:32:01  127.0.0.1     /index.html              200 OK       
    2026-04-10 14:32:05  127.0.0.1     /missing.jpg             404 Not Found

"""

import threading
import datetime
import os


class ServerLogger:
    """
    Thread-safe append-only logger.

    Uses a threading.Lock to prevent two threads from writing to the log
    file at the same time (which could corrupt entries).

    Parameters
    ----------
    log_path : str
        Path to the log file. Directories are created automatically.
    """

    def __init__(self, log_path: str):
        self.log_path = log_path
        self._lock = threading.Lock()   # one write at a time across all threads

        # Create parent directories if they don't exist yet
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        # Write a header line if this is a new/empty file
        if not os.path.isfile(log_path) or os.path.getsize(log_path) == 0:
            self._write_header()

    # ── Public API ────────────────────────────────────────────────────────────

    def log(self, client_ip: str, requested_path: str, status: str) -> None:
        """
        Append one log entry.

        Parameters
        ----------
        client_ip      : e.g. "127.0.0.1"
        requested_path : e.g. "/index.html" or "BAD_REQUEST"
        status         : e.g. "200 OK", "404 Not Found"
        status         : e.g. "200 OK", "404 Not Found"
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp}\t{client_ip}\t{requested_path}\t\t{status}\n"

        # Acquire the lock so only one thread writes at a time
        with self._lock:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(line)

    # ── Private ───────────────────────────────────────────────────────────────

    def _write_header(self) -> None:
        """Write a human-readable column header at the top of the log file."""
        header = (
            "# Comp 2322 Web Server — Request Log\n"
            "# Format: TIMESTAMP  CLIENT-IP  PATH  STATUS\n"
            f"# Started: {datetime.datetime.now()}\n"
            "#\n"
            "TIMESTAMP\t\t\tCLIENT-IP\tPATH\t\t\tSTATUS\n"
            + "-" * 80 + "\n"
        )
        with open(self.log_path, "w", encoding="utf-8") as fh:
            fh.write(header)
