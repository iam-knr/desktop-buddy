import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
MODE = {"reply": None}       # function(prompt, system, fmt) -> response text
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        body = json.dumps({"models": [{"name": "qwen2.5:1.5b"}]}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        out = MODE["reply"](req.get("prompt", ""), req.get("system", ""), req.get("format")) if MODE["reply"] and req.get("prompt") else ""
        body = json.dumps({"response": out}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(body)
def start():
    s = HTTPServer(("127.0.0.1", 11434), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s
