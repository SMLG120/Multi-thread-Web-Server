"""
server.py — Multi-Threaded HTTP Web Server
COMP2322 Computer Networking Project

Author: Samuel Ha
Student ID: 25142247X

This module is the entry point. It:
  1. Creates a TCP server socket and binds it to HOST:PORT
  2. Listens for incoming connections in an infinite loop
  3. Spawns a new daemon thread for every accepted connection
  4. Delegates all request/response logic to ClientHandler
"""

import socket
import threading
import os
import sys

from utils.logger import ServerLogger
from utils.request_parser import HTTPRequestParser, MalformedRequestError
from utils.response_builder import HTTPResponseBuilder

# ── Server Configuration ──────────────────────────────────────────────────────
HOST = "127.0.0.1"          # Loopback address; change to "" for all interfaces
PORT = 8080                  # Avoid 80 if another web server is already running
STATIC_DIR = "static"        # Directory that holds all serveable files
LOG_FILE = "logs/server.log" # Path to the log file (directory must exist)

# How long to wait (seconds) for the next request on a keep-alive connection
KEEPALIVE_TIMEOUT = 10

# ── Main Server Class ─────────────────────────────────────────────────────────

class WebServer:
    """Owns the listening socket and the accept-loop."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        print(LOG_FILE)
        self.logger = ServerLogger(LOG_FILE)

        # AF_INET  → IPv4
        # SOCK_STREAM → TCP (reliable, connection-oriented)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # SO_REUSEADDR lets us restart the server immediately without
        # waiting for the OS to release the port (avoids "Address in use").
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start(self):
        """Bind, listen, and enter the accept-loop."""
        self.server_socket.bind((self.host, self.port))

        # backlog=10 → OS can queue up to 10 pending connections
        self.server_socket.listen(10)
        print(f"[SERVER] Listening on http://{self.host}:{self.port}")
        print(f"[SERVER] Serving files from '{STATIC_DIR}/'")
        print(f"[SERVER] Press Ctrl+C to stop.\n")

        try:
            while True:
                # Block here until a client connects; returns a new socket
                # dedicated to that single client and the client's address.
                conn, addr = self.server_socket.accept()
                print(f"[CONNECT] New connection from {addr[0]}:{addr[1]}")

                # Create a handler and run it in a dedicated daemon thread so
                # the main thread can keep accepting new connections immediately.
                handler = ClientHandler(conn, addr, self.logger)
                thread = threading.Thread(target=handler.handle, daemon=True)
                thread.start()

        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down gracefully.")
        finally:
            self.server_socket.close()


# ── Per-Connection Handler ────────────────────────────────────────────────────

class ClientHandler:
    """
    Handles *all* HTTP requests that arrive on a single TCP connection.

    For persistent connections (Connection: keep-alive) the loop runs until
    the client closes the connection or the keep-alive timeout expires.
    For non-persistent connections (Connection: close) it exits after one
    request/response cycle.
    """

    def __init__(self, conn: socket.socket, addr: tuple, logger: ServerLogger):
        self.conn = conn
        self.client_ip = addr[0]
        self.logger = logger
        self.parser = HTTPRequestParser()
        self.builder = HTTPResponseBuilder(STATIC_DIR)

    def handle(self):
        """Main loop: read → parse → respond (repeat for keep-alive)."""
        keep_alive = True   # assume persistent until told otherwise

        try:
            while keep_alive:
                # Set a timeout so we don't block forever on idle connections
                self.conn.settimeout(KEEPALIVE_TIMEOUT)

                raw_request = self._receive_request()

                # Empty data means the client closed the connection
                if not raw_request:
                    break

                try:
                    request = self.parser.parse(raw_request)
                except MalformedRequestError:
                    # Send 400 and close; no point keeping a bad connection alive
                    response = self.builder.build_400()
                    self.conn.sendall(response)
                    self.logger.log(self.client_ip, "BAD_REQUEST", "400 Bad Request")
                    break

                # Decide persistence BEFORE building the response so the
                # response can echo back the correct Connection header.
                connection_header = request.headers.get("connection", "").lower()
                if connection_header == "close":
                    keep_alive = False
                elif connection_header == "keep-alive":
                    keep_alive = True
                else:
                    # HTTP/1.1 defaults to keep-alive; HTTP/1.0 defaults to close
                    keep_alive = (request.version == "HTTP/1.1")

                # Build and send the response
                response, status = self.builder.build_response(request, keep_alive)
                self.conn.sendall(response)

                # Write one line to the log file
                self.logger.log(
                    self.client_ip,
                    request.path,
                    status
                )

                print(
                    f"[{status}] {request.method} {request.path}"
                    f" — {self.client_ip}"
                    f" ({'keep-alive' if keep_alive else 'close'})"
                )

        except socket.timeout:
            # Keep-alive timeout: client was idle too long → close silently
            pass
        except Exception as exc:
            print(f"[ERROR] Unexpected error: {exc}")
        finally:
            self.conn.close()

    def _receive_request(self) -> bytes:
        """
        Read bytes from the socket until we see the blank line that marks
        the end of HTTP headers (\\r\\n\\r\\n).  Returns the raw bytes or an
        empty bytes object if the connection was closed by the peer.
        """
        data = b""
        while True:
            try:
                chunk = self.conn.recv(4096)
            except socket.timeout:
                raise   # propagate so the outer handler can close cleanly
            if not chunk:
                return b""  # client closed the connection
            data += chunk
            if b"\r\n\r\n" in data:
                return data


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Allow overriding the port on the command line: python server.py 9090
    if len(sys.argv) == 2:
        PORT = int(sys.argv[1])

    # Make sure required directories exist before starting
    os.makedirs("logs", exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)

    server = WebServer(HOST, PORT)
    server.start()
