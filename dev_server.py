import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend"))
print("Frontend on http://localhost:5500  (Ctrl+C to stop)")
ThreadingHTTPServer(("127.0.0.1", 5500), NoCache).serve_forever()
