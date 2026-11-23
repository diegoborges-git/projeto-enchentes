from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parent.parent


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(302)
            self.send_header("Location", "/app/")
            self.end_headers()
            return
        super().do_GET()


os.chdir(ROOT)
print("Mapa disponível em http://localhost:8000")
ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
