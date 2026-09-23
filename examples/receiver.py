"""Local-only teaching receiver: fail, recover, then deduplicate in memory."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=9001)
parser.add_argument("--fail-first", type=int, default=1)
args = parser.parse_args()
lock = Lock()
seen = set()
attempts = 0


class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        global attempts
        if self.path != "/webhook":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if not 0 <= length <= 262_144:
            self.send_error(413)
            return
        self.rfile.read(length)
        key = self.headers.get("Idempotency-Key")
        if not key:
            self.send_error(400, "Idempotency-Key required")
            return
        with lock:
            attempts += 1
            if attempts <= args.fail_first:
                status, outcome = 503, "simulated_failure"
            elif key in seen:
                status, outcome = 200, "deduplicated"
            else:
                seen.add(key)
                status, outcome = 200, "processed"
            processed = len(seen)
        result = json.dumps({"outcome": outcome, "processed_events": processed}).encode()
        print(f"HTTP {status} | {outcome} | processed_events={processed}", flush=True)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(result)))
        self.end_headers()
        self.wfile.write(result)

    def log_message(self, *_args):
        pass


print(f"Local receiver on http://127.0.0.1:{args.port}/webhook", flush=True)
ThreadingHTTPServer(("127.0.0.1", args.port), Receiver).serve_forever()
