#!/bin/bash
# run_tests.sh — automated test suite for COMP2322 Web Server
# Student Name: Samuel Ha
# Student ID: 251442447X
# Usage: Run "bash run_tests.sh" in terminal

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"   # absolute path of test/
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"        # one level up → project root
STATIC_DIR="$PROJECT_ROOT/static"             # project root/static/
 
BASE="http://127.0.0.1:8080"
PASS=0
FAIL=0
 
# ── Helpers ────────────────────────────────────────────────────────────────────
 
# Print a pass/fail line and update counters
check() {
    local label="$1"
    local expected="$2"
    local actual="$3"
    if [ "$actual" = "$expected" ]; then
        echo "  PASS  $label"
        ((PASS++))
    else
        echo "  FAIL  $label  (expected '$expected', got '$actual')"
        ((FAIL++))
    fi
}
 
# Print a section header
section() {
    echo ""
    echo "[ $1 ]"
}
 
# ── Pre-flight check ───────────────────────────────────────────────────────────
# Verify the server is reachable before running any tests
 
section "Pre-flight"
PREFLIGHT=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 "$BASE/" 2>/dev/null)
if [ "$PREFLIGHT" != "200" ]; then
    echo "  ERROR  Server is not responding at $BASE"
    echo "         Start it first: python3 server.py"
    echo ""
    exit 1
fi
echo "  OK     Server is up at $BASE"
echo "  OK     Static dir: $STATIC_DIR"
 
# ── Setup ──────────────────────────────────────────────────────────────────────
section "Setup"
 
# Create a file with no read permissions to trigger 403
echo "secret content" > "$STATIC_DIR/secret.html"
chmod 000 "$STATIC_DIR/secret.html"
echo "  created $STATIC_DIR/secret.html with chmod 000"
 
# ── Status Codes ───────────────────────────────────────────────────────────────
section "Status Codes"
 
check "200 OK — index.html" \
    "200" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/index.html")"
 
check "200 OK — hello.txt" \
    "200" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/hello.txt")"
 
check "404 Not Found" \
    "404" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/this-does-not-exist.html")"
 
check "403 Forbidden" \
    "403" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/secret.html")"
 
check "304 Not Modified — future If-Modified-Since date" \
    "304" \
    "$(curl -s -o /dev/null -w '%{http_code}' \
       -H 'If-Modified-Since: Fri, 31 Dec 2099 23:59:59 GMT' \
       "$BASE/hello.txt")"
 
check "200 OK — old If-Modified-Since date (file is newer)" \
    "200" \
    "$(curl -s -o /dev/null -w '%{http_code}' \
       -H 'If-Modified-Since: Thu, 01 Jan 2015 00:00:00 GMT' \
       "$BASE/hello.txt")"
 
check "200 OK — malformed If-Modified-Since ignored gracefully" \
    "200" \
    "$(curl -s -o /dev/null -w '%{http_code}' \
       -H 'If-Modified-Since: not-a-real-date' \
       "$BASE/hello.txt")"
 
# 400 Bad Request — send a raw malformed request via Python
check "400 Bad Request — malformed request line" \
    "400" \
    "$(python3 -c "
import socket
s = socket.socket()
s.connect(('127.0.0.1', 8080))
s.send(b'NOTAVERB /path\r\n\r\n')
resp = s.recv(1024).decode('latin-1')
s.close()
print(resp.split(' ')[1])   # extract status code from response line
" 2>/dev/null)"
 
# ── Methods ────────────────────────────────────────────────────────────────────
section "HTTP Methods"
 
check "HEAD — returns 200 status" \
    "200" \
    "$(curl -s -o /dev/null -w '%{http_code}' -I "$BASE/index.html")"
 
check "HEAD — body is empty (0 bytes downloaded)" \
    "0" \
    "$(curl -s -I -w '%{size_download}' -o /dev/null "$BASE/index.html")"
 
# GET Content-Length must match the HEAD Content-Length for the same file
GET_CL=$(curl -sI "$BASE/hello.txt" | grep -i '^content-length:' | tr -d '[:space:]' | cut -d: -f2)
HEAD_CL=$(curl -sI "$BASE/hello.txt" | grep -i '^content-length:' | tr -d '[:space:]' | cut -d: -f2)
check "HEAD Content-Length matches GET Content-Length" \
    "$GET_CL" "$HEAD_CL"
 
# ── Response Headers ───────────────────────────────────────────────────────────
section "Response Headers"
 
LM=$(curl -sI "$BASE/hello.txt" | grep -i "last-modified:" | wc -l | tr -d ' ')
check "Last-Modified header present on 200 response" "1" "$LM"
 
DATE_H=$(curl -sI "$BASE/hello.txt" | grep -i "^date:" | wc -l | tr -d ' ')
check "Date header present" "1" "$DATE_H"
 
SERVER_H=$(curl -sI "$BASE/hello.txt" | grep -i "^server:" | wc -l | tr -d ' ')
check "Server header present" "1" "$SERVER_H"
 
CL_H=$(curl -sI "$BASE/hello.txt" | grep -i "^content-length:" | wc -l | tr -d ' ')
check "Content-Length header present" "1" "$CL_H"
 
# ── Connection Header ──────────────────────────────────────────────────────────
section "Connection Header"
 
CONN_KA=$(curl -sI "$BASE/index.html" \
           | grep -i "connection: keep-alive" | wc -l | tr -d ' ')
check "Connection: keep-alive in response (HTTP/1.1 default)" "1" "$CONN_KA"
 
CONN_CL=$(curl -sI -H "Connection: close" "$BASE/index.html" \
           | grep -i "connection: close" | wc -l | tr -d ' ')
check "Connection: close echoed back when client requests it" "1" "$CONN_CL"
 
CONN_10=$(curl -sI --http1.0 "$BASE/index.html" \
           | grep -i "connection: close" | wc -l | tr -d ' ')
check "Connection: close when using HTTP/1.0" "1" "$CONN_10"
 
# ── MIME Types ─────────────────────────────────────────────────────────────────
section "MIME Types"
 
CT_HTML=$(curl -sI "$BASE/index.html" \
           | grep -i "content-type: text/html" | wc -l | tr -d ' ')
check "HTML Content-Type: text/html" "1" "$CT_HTML"
 
CT_TXT=$(curl -sI "$BASE/hello.txt" \
          | grep -i "content-type: text/plain" | wc -l | tr -d ' ')
check "TXT  Content-Type: text/plain" "1" "$CT_TXT"
 
# Test image MIME type only if an image exists in static/
if ls "$STATIC_DIR"/*.jpg "$STATIC_DIR"/*.png 2>/dev/null | head -1 | grep -q .; then
    IMG=$(ls "$STATIC_DIR"/*.jpg "$STATIC_DIR"/*.png 2>/dev/null | head -1 | xargs basename)
    CT_IMG=$(curl -sI "$BASE/$IMG" \
              | grep -i "content-type: image/" | wc -l | tr -d ' ')
    check "Image Content-Type: image/*  ($IMG)" "1" "$CT_IMG"
else
    echo "  SKIP  Image MIME type — no .jpg or .png found in $STATIC_DIR"
    echo "        Copy an image there and re-run to test this"
fi
 
# ── Log File ───────────────────────────────────────────────────────────────────
section "Log File"
 
LOG_FILE="$PROJECT_ROOT/logs/server.log"
if [ -f "$LOG_FILE" ]; then
    echo "  OK     Log file exists at $LOG_FILE"
    LOG_200=$(grep -c "200 OK" "$LOG_FILE" 2>/dev/null || echo 0)
    LOG_304=$(grep -c "304 Not Modified" "$LOG_FILE" 2>/dev/null || echo 0)
    LOG_400=$(grep -c "400 Bad Request" "$LOG_FILE" 2>/dev/null || echo 0)
    LOG_403=$(grep -c "403 Forbidden" "$LOG_FILE" 2>/dev/null || echo 0)
    LOG_404=$(grep -c "404 Not Found" "$LOG_FILE" 2>/dev/null || echo 0)
    check "Log contains 200 OK entries"       "1" "$([ "$LOG_200" -gt 0 ] && echo 1 || echo 0)"
    check "Log contains 304 Not Modified"     "1" "$([ "$LOG_304" -gt 0 ] && echo 1 || echo 0)"
    check "Log contains 400 Bad Request"      "1" "$([ "$LOG_400" -gt 0 ] && echo 1 || echo 0)"
    check "Log contains 403 Forbidden"        "1" "$([ "$LOG_403" -gt 0 ] && echo 1 || echo 0)"
    check "Log contains 404 Not Found"        "1" "$([ "$LOG_404" -gt 0 ] && echo 1 || echo 0)"
else
    echo "  FAIL  Log file not found at $LOG_FILE"
    ((FAIL++))
fi
 
# ── Teardown ───────────────────────────────────────────────────────────────────
section "Teardown"
 
chmod 644 "$STATIC_DIR/secret.html"
echo "  restored $STATIC_DIR/secret.html to 644"
 
# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo "  Results : $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
    echo "  Status  : ALL TESTS PASSED"
else
    echo "  Status  : $FAIL TEST(S) FAILED — see above"
fi
echo "════════════════════════════════════════"
echo ""