import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class RemoteDashboard:
    """Small LAN dashboard for status and text commands, protected by a token."""

    def __init__(self, brain, host="0.0.0.0", port=8000):
        self.brain = brain
        self.host = host
        self.port = port
        self.token = secrets.token_urlsafe(18)
        self.server = None
        self.thread = None

    def start(self):
        brain = self.brain
        token = self.token

        class Handler(BaseHTTPRequestHandler):
            def _authorized(self):
                return self.headers.get("X-JARVIS-TOKEN") == token

            def _json(self, status, payload):
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/":
                    body = (
                        "<!doctype html><meta charset='utf-8'>"
                        "<title>JARVIS Remote Control</title>"
                        "<style>body{font:16px sans-serif;background:#07121b;color:#d8faff;"
                        "max-width:720px;margin:40px auto}button{padding:10px;background:#0bb;"
                        "border:0}textarea{width:100%;height:100px}</style>"
                        "<h1>J.A.R.V.I.S. Remote Control</h1>"
                        "<p>Token in das Feld eintragen. Befehle werden lokal verarbeitet.</p>"
                        "<input id='t' type='password' placeholder='X-JARVIS-TOKEN' style='width:100%'>"
                        "<textarea id='p' placeholder='Befehl'></textarea><button onclick='ask()'>Senden</button>"
                        "<pre id='r'></pre><script>"
                        "async function ask(){let h={'Content-Type':'application/json',"
                        "'X-JARVIS-TOKEN':document.getElementById('t').value};"
                        "let p=document.getElementById('p').value;"
                        "let r=await fetch('/api/ask',{method:'POST',headers:h,body:JSON.stringify({prompt:p})});"
                        "document.getElementById('r').textContent=JSON.stringify(await r.json(),null,2)}"
                        "</script>"
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path != "/api/status":
                    self._json(404, {"error": "not_found"})
                    return
                self._json(200, {
                    "ok": True,
                    "model": brain.model,
                    "ollama": brain.is_active,
                    "plugins": brain.plugins.list(),
                    "audio": brain.audio_devices.status(),
                    "screen_capture": "available",
                })

            def do_POST(self):
                if not self._authorized():
                    self._json(403, {"error": "invalid_token"})
                    return
                if self.path != "/api/ask":
                    self._json(404, {"error": "not_found"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length))
                    prompt = str(payload.get("prompt", "")).strip()
                    if not prompt:
                        self._json(400, {"error": "prompt_required"})
                        return
                    self._json(200, {"response": brain.process_request(prompt)})
                except (ValueError, json.JSONDecodeError):
                    self._json(400, {"error": "invalid_json"})

            def log_message(self, *_args):
                return

        self.server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.token

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
