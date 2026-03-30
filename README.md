# COMP2322 — Multi-Threaded HTTP Web Server

> A lightweight HTTP/1.1 web server built from scratch using Python's `socket` module.  
> No `http.server`, no `HTTPServer` — pure socket programming.

---

## 📋 Features

| Feature | Details |
|---|---|
| **Multi-threading** | Each client connection runs in its own daemon thread |
| **Methods** | `GET` (text + images) and `HEAD` |
| **Status codes** | `200 OK`, `304 Not Modified`, `400 Bad Request`, `403 Forbidden`, `404 Not Found` |
| **Caching headers** | `Last-Modified` (sent) and `If-Modified-Since` (parsed) |
| **Persistence** | `Connection: keep-alive` and `Connection: close` |
| **Logging** | One tab-separated line per request appended to `logs/server.log` |
| **MIME types** | `.html`, `.txt`, `.css`, `.js`, `.jpg`, `.png`, `.gif`, `.ico`, `.pdf`, … |

---

## 🧰 Requirements

- **Python 3.8+** (no third-party packages required — standard library only)
- A terminal / command prompt

Check your Python version:
```bash
python3 --version
```

---

## 📁 Project Structure

```
webserver/
├── server.py                 ← Entry point — run this file
├── utils/
│   ├── __init__.py
│   ├── request_parser.py     ← Parses raw HTTP request bytes
│   ├── response_builder.py   ← Builds HTTP response bytes
│   └── logger.py             ← Thread-safe request logger
├── static/                   ← Files served to clients
│   ├── index.html
│   ├── hello.txt
│   ├── 404.html
│   └── image.png             ← (add your own images here)
├── logs/
│   └── server.log            ← Auto-created on first run
└── README.md
```

---

## 🚀 How to Run

### 1. Clone / download the project

```bash
git clone https://github.com/<your-username>/comp2322-webserver.git
cd comp2322-webserver
```

### 2. Start the server (default port 8080)

```bash
python3 server.py
```

### 3. Override the port (optional)

```bash
python3 server.py 9090
```

The server prints:

```
[SERVER] Listening on http://127.0.0.1:8080
[SERVER] Serving files from 'static/'
[SERVER] Press Ctrl+C to stop.
```

### 4. Open your browser

Navigate to: **http://127.0.0.1:8080**

---

## 🧪 Testing with curl

### Basic GET request
```bash
curl http://127.0.0.1:8080/index.html
```

### HEAD request (headers only, no body)
```bash
curl -I http://127.0.0.1:8080/index.html
```

### Verbose output (see all headers)
```bash
curl -v http://127.0.0.1:8080/hello.txt
```

### 404 Not Found
```bash
curl -v http://127.0.0.1:8080/does-not-exist.html
```

### 304 Not Modified (conditional GET)
```bash
# First, get the Last-Modified date
curl -I http://127.0.0.1:8080/index.html

# Then send If-Modified-Since with that date
curl -v -H "If-Modified-Since: Wed, 01 Jan 2026 00:00:00 GMT" \
        http://127.0.0.1:8080/index.html
```

### Non-persistent connection (HTTP/1.0 style)
```bash
curl --http1.0 http://127.0.0.1:8080/index.html
```

### Explicit Connection: close
```bash
curl -v -H "Connection: close" http://127.0.0.1:8080/index.html
```

### Multiple simultaneous clients (stress test)
```bash
for i in {1..10}; do
    curl -s http://127.0.0.1:8080/index.html > /dev/null &
done
wait
echo "All done."
```

---

## 📝 Log File Format

`logs/server.log` is appended with one entry per request:

```
TIMESTAMP               CLIENT-IP       PATH            STATUS
--------------------------------------------------------------------------------
2026-04-10 14:32:01     127.0.0.1       /index.html     200 OK
2026-04-10 14:32:05     127.0.0.1       /hello.txt      200 OK
2026-04-10 14:32:10     127.0.0.1       /missing.html   404 Not Found
2026-04-10 14:32:15     127.0.0.1       /index.html     304 Not Modified
```

---

## ➕ Adding Files to Serve

Place any file inside the `static/` directory and it becomes immediately accessible:

```bash
cp ~/my-photo.jpg static/
# Now accessible at: http://127.0.0.1:8080/my-photo.jpg
```

---

## 🔒 Security Notes

- **Path traversal**: requests containing `..` are rejected with 400.
- **Forbidden files**: files without read permission return 403.
- **Static directory only**: files outside `static/` are inaccessible.

---

## 👤 Author

- **Name**: Samuel Ha  
- **Student ID**: 25142247X
- **Course**: COMP2322 Computer Networking, PolyU  
- **Due**: April 26, 2026
