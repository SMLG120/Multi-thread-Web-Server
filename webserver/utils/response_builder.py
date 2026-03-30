"""
utils/response_builder.py — HTTP Response Builder

Builds well-formed HTTP/1.1 response bytes for every status code required
by the project rubric:

    200 OK
    304 Not Modified
    400 Bad Request
    403 Forbidden
    404 Not Found

Also handles:
  • GET vs HEAD   (HEAD omits the body)
  • Last-Modified / If-Modified-Since
  • Connection: keep-alive / close
  • MIME-type detection (text, images, …)
"""

import os
import stat
import email.utils          # RFC 2822 date formatting/parsing
import datetime
from typing import Tuple

from utils.request_parser import HTTPRequest


# ── MIME-Type Map ─────────────────────────────────────────────────────────────
# Maps lowercase file extensions → Content-Type values.
# Add more as needed.
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".htm":  "text/html; charset=utf-8",
    ".txt":  "text/plain; charset=utf-8",
    ".css":  "text/css",
    ".js":   "application/javascript",
    ".json": "application/json",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".gif":  "image/gif",
    ".ico":  "image/x-icon",
    ".svg":  "image/svg+xml",
    ".pdf":  "application/pdf",
}

DEFAULT_MIME = "application/octet-stream"   # fall-back for unknown extensions


# ── Response Builder ──────────────────────────────────────────────────────────

class HTTPResponseBuilder:
    """
    Builds complete HTTP response byte strings ready to send over a socket.

    Parameters
    ----------
    static_dir : str
        Filesystem path to the directory that holds serveable files.
        All requested paths are resolved relative to this directory.
    """

    def __init__(self, static_dir: str):
        # Convert to absolute path so we can do security checks later
        self.static_dir = os.path.abspath(static_dir)

    # ── Public API ────────────────────────────────────────────────────────────

    def build_response(
        self, request: HTTPRequest, keep_alive: bool
    ) -> Tuple[bytes, str]:
        """
        Dispatch to the appropriate handler based on the resolved file state.

        Returns
        -------
        (response_bytes, status_string)
            status_string is used by the logger, e.g. "200 OK".
        """
        # Resolve the URI path to a filesystem path safely
        file_path = self._resolve_path(request.path)

        # ── 403 Forbidden: path exists but is not readable ────────────────
        if os.path.exists(file_path):
            file_stat = os.stat(file_path)
            # Check if owner-read bit is set (simplified permission check)
            if not (file_stat.st_mode & stat.S_IRUSR):
                return self.build_403(request, keep_alive), "403 Forbidden"

        # ── 404 Not Found ────────────────────────────────────────────────
        if not os.path.isfile(file_path):
            return self.build_404(request, keep_alive), "404 Not Found"

        # ── 304 Not Modified (conditional GET) ───────────────────────────
        ims_header = request.headers.get("if-modified-since", "")
        if ims_header:
            try:
                ims_time = email.utils.parsedate_to_datetime(ims_header)
                # Truncate file mtime to whole seconds for comparison
                file_mtime = datetime.datetime.fromtimestamp(
                    os.path.getmtime(file_path),
                    tz=datetime.timezone.utc
                ).replace(microsecond=0)

                if file_mtime <= ims_time:
                    return self.build_304(request, keep_alive), "304 Not Modified"
            except Exception:
                # If the header is malformed, just ignore it and serve normally
                pass

        # ── 200 OK ───────────────────────────────────────────────────────
        return self.build_200(request, file_path, keep_alive), "200 OK"

    def build_400(self) -> bytes:
        """400 Bad Request — called before a valid request object exists."""
        body = self._error_html(400, "Bad Request",
                                "The server could not understand your request.")
        headers = self._base_headers(400, "Bad Request", len(body),
                                     "text/html; charset=utf-8",
                                     keep_alive=False)
        return headers + body

    # ── Private builders ──────────────────────────────────────────────────────

    def build_200(
        self, request: HTTPRequest, file_path: str, keep_alive: bool
    ) -> bytes:
        """Read the file and return a complete 200 response."""
        with open(file_path, "rb") as fh:
            body = fh.read()

        mime = self._mime_for(file_path)
        mtime = os.path.getmtime(file_path)
        last_modified = email.utils.formatdate(mtime, usegmt=True)

        headers = self._base_headers(200, "OK", len(body), mime, keep_alive)
        headers += f"Last-Modified: {last_modified}\r\n".encode()
        headers += b"\r\n"   # blank line ends headers

        # HEAD responses contain headers but NO body
        if request.method == "HEAD":
            return headers

        return headers + body

    def build_304(self, request: HTTPRequest, keep_alive: bool) -> bytes:
        """304 Not Modified — no body, no Content-Type."""
        headers  = b"HTTP/1.1 304 Not Modified\r\n"
        headers += f"Date: {self._now()}\r\n".encode()
        headers += f"Connection: {'keep-alive' if keep_alive else 'close'}\r\n".encode()
        headers += b"\r\n"
        return headers

    def build_403(self, request: HTTPRequest, keep_alive: bool) -> bytes:
        """403 Forbidden."""
        body = self._error_html(403, "Forbidden",
                                "You do not have permission to access this resource.")
        headers = self._base_headers(403, "Forbidden", len(body),
                                     "text/html; charset=utf-8", keep_alive)
        headers += b"\r\n"
        if request.method == "HEAD":
            return headers
        return headers + body

    def build_404(self, request: HTTPRequest, keep_alive: bool) -> bytes:
        """404 Not Found — serve a custom error page if one exists."""
        custom = os.path.join(self.static_dir, "404.html")
        if os.path.isfile(custom):
            with open(custom, "rb") as fh:
                body = fh.read()
        else:
            body = self._error_html(404, "Not Found",
                                    "The requested file could not be found on this server.")
        headers = self._base_headers(404, "Not Found", len(body),
                                     "text/html; charset=utf-8", keep_alive)
        headers += b"\r\n"
        if request.method == "HEAD":
            return headers
        return headers + body

    # ── Helper Methods ────────────────────────────────────────────────────────

    def _resolve_path(self, uri_path: str) -> str:
        """
        Convert a URI path like '/images/cat.jpg' to an absolute filesystem
        path inside self.static_dir.

        We use os.path.realpath to follow symlinks and then check the result
        still starts with static_dir — this is the second line of defence
        against path-traversal attacks (the parser is the first).
        """
        # Strip the leading slash so os.path.join works correctly
        relative = uri_path.lstrip("/")
        candidate = os.path.realpath(os.path.join(self.static_dir, relative))

        # Guarantee the resolved path is inside static_dir
        if not candidate.startswith(self.static_dir + os.sep) and \
           candidate != self.static_dir:
            # Treat attempted escapes as 403 (file won't exist anyway)
            return ""

        return candidate

    def _base_headers(
        self,
        status_code: int,
        reason: str,
        content_length: int,
        content_type: str,
        keep_alive: bool,
    ) -> bytes:
        """Return the response-line + mandatory headers (without trailing \\r\\n)."""
        connection_val = "keep-alive" if keep_alive else "close"
        headers  = f"HTTP/1.1 {status_code} {reason}\r\n".encode()
        headers += f"Date: {self._now()}\r\n".encode()
        headers += f"Server: Comp2322-WebServer/1.0\r\n".encode()
        headers += f"Content-Type: {content_type}\r\n".encode()
        headers += f"Content-Length: {content_length}\r\n".encode()
        headers += f"Connection: {connection_val}\r\n".encode()
        return headers

    @staticmethod
    def _mime_for(file_path: str) -> str:
        """Return the MIME type for a file based on its extension."""
        _, ext = os.path.splitext(file_path)
        return MIME_TYPES.get(ext.lower(), DEFAULT_MIME)

    @staticmethod
    def _now() -> str:
        """Return the current UTC time in RFC 2822 / HTTP-date format."""
        return email.utils.formatdate(usegmt=True)

    @staticmethod
    def _error_html(code: int, reason: str, detail: str) -> bytes:
        """Generate a minimal HTML error page as bytes."""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{code} {reason}</title>
  <style>
    body {{ font-family: monospace; background:#111; color:#eee;
           display:flex; flex-direction:column; align-items:center;
           justify-content:center; height:100vh; margin:0; }}
    h1   {{ font-size:5rem; margin:0; color:#e55; }}
    p    {{ font-size:1.2rem; color:#aaa; }}
  </style>
</head>
<body>
  <h1>{code}</h1>
  <h2>{reason}</h2>
  <p>{detail}</p>
  <p><a href="/" style="color:#7af">← Back to Home</a></p>
</body>
</html>"""
        return html.encode("utf-8")
