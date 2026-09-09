#!/usr/bin/env python3
"""hitl_serve.py — HITL server with DURABLE rulings (replaces plain http.server).

Serves the batch folder like before, plus:
  POST /save     one ruling (JSON) -> appended to judgments_autosave.jsonl on disk
  GET  /saved    all rulings so far (latest per paper) -> the viewer restores them
                 on load, in ANY browser, private window or not.

Run from the batch folder:  python3 hitl_serve.py [port]   (default 8766)
Every ruling is on disk the moment the key is pressed. Ctrl-C to stop."""
import json, sys
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
STORE = Path("judgments_autosave.jsonl")

def latest():
    out = {}
    if STORE.exists():
        for line in STORE.read_text().splitlines():
            try:
                r = json.loads(line)
                out[r["paper_id"]] = r
            except Exception:
                pass
    return out

class H(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") == "/saved":
            body = json.dumps(latest()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.rstrip("/") == "/save":
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n)
            try:
                rec = json.loads(raw)
                assert rec.get("paper_id")
                with STORE.open("a") as f:
                    f.write(json.dumps(rec) + "\n")
                self.send_response(200)
            except Exception:
                self.send_response(400)
            self.end_headers()
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, fmt, *a):  # quiet
        pass

if __name__ == "__main__":
    print(f"HITL server on http://localhost:{PORT}/hitl_field_viewer.html")
    print(f"rulings persist to {STORE.resolve()} as you press keys")
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()
