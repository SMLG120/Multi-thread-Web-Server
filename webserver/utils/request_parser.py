"""
utils/request_parser.py — HTTP Request Parser

Parses the raw bytes received from the client socket into a structured
HTTPRequest object that the rest of the server can work with easily.

Supported methods : GET, HEAD
Supported versions: HTTP/1.0, HTTP/1.1
"""

from dataclasses import dataclass, field
from typing import Dict


# ── Exception ─────────────────────────────────────────────────────────────────

class MalformedRequestError(Exception):
    """Raised when the request cannot be parsed (triggers a 400 response)."""


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class HTTPRequest:
    """
    Represents a parsed HTTP request.

    Attributes
    ----------
    method  : HTTP verb in UPPER-CASE (e.g. 'GET', 'HEAD')
    path    : Requested URI path   (e.g. '/index.html', '/images/cat.jpg')
    version : HTTP version string  (e.g. 'HTTP/1.1')
    headers : Dict of lower-cased header names → values
              (lower-casing makes look-ups case-insensitive)
    """
    method: str
    path: str
    version: str
    headers: Dict[str, str] = field(default_factory=dict)


# ── Parser ────────────────────────────────────────────────────────────────────

class HTTPRequestParser:
    """Stateless parser; create one instance per ClientHandler thread."""

    def parse(self, raw_data: bytes) -> HTTPRequest:
        """
        Parse raw socket bytes into an HTTPRequest.

        Parameters
        ----------
        raw_data : bytes
            Everything received from the socket up to and including \\r\\n\\r\\n.

        Returns
        -------
        HTTPRequest

        Raises
        ------
        MalformedRequestError
            If the request line is missing, unrecognisable, or the method is
            unsupported.
        """
        try:
            # Decode as latin-1 (superset of ASCII, won't fail on 8-bit bytes)
            text = raw_data.decode("latin-1")
        except Exception:
            raise MalformedRequestError("Cannot decode request bytes.")

        # Split headers section from any body (we ignore body for GET/HEAD)
        header_section = text.split("\r\n\r\n", 1)[0]
        lines = header_section.split("\r\n")

        if not lines:
            raise MalformedRequestError("Empty request.")

        # ── Request Line ─────────────────────────────────────────────────────
        # Format: METHOD SP Request-URI SP HTTP-Version
        request_line = lines[0]
        parts = request_line.split()

        if len(parts) != 3:
            raise MalformedRequestError(
                f"Bad request line: '{request_line}'"
            )

        method, raw_path, version = parts

        # Validate method — only GET and HEAD are required by the rubric
        method = method.upper()
        if method not in ("GET", "HEAD"):
            raise MalformedRequestError(f"Unsupported method: {method}")

        # Validate HTTP version
        if version not in ("HTTP/1.0", "HTTP/1.1"):
            raise MalformedRequestError(f"Unsupported HTTP version: {version}")

        # ── Path Sanitisation ────────────────────────────────────────────────
        # Strip query strings (e.g. /page.html?foo=bar → /page.html)
        path = raw_path.split("?")[0]

        # Map bare "/" to the default page
        if path == "/":
            path = "/index.html"

        # Security: reject any path that tries to escape the static directory
        # by using ".." segments.
        if ".." in path:
            raise MalformedRequestError("Path traversal attempt detected.")

        # ── Headers ──────────────────────────────────────────────────────────
        headers: Dict[str, str] = {}
        for line in lines[1:]:
            if ":" not in line:
                continue  # skip malformed header lines gracefully
            key, _, value = line.partition(":")
            # Store with lower-cased key so callers don't need to worry about
            # case (HTTP headers are case-insensitive per RFC 7230)
            headers[key.strip().lower()] = value.strip()

        return HTTPRequest(
            method=method,
            path=path,
            version=version,
            headers=headers,
        )
