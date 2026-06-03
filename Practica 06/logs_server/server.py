"""
Servidor de logs remoto para la Pico W.

- Escucha en UDP/9999 los mensajes de log que envía la Pico.
- Sirve en HTTP/8080 una página web con los logs en vivo (Server-Sent Events).
- Solo stdlib de Python — no requiere pip install nada.

Uso:
    python server.py

Después abre http://localhost:8080 en el navegador.
"""

import http.server
import queue
import socket
import threading
import time
from socketserver import ThreadingMixIn

LOG_PORT = 9999       # debe coincidir con LOG_PORT en main.py de la Pico
WEB_PORT = 8080
MAX_HISTORY = 500     # mensajes que retiene en memoria para nuevos clientes

_history = []
_history_lock = threading.Lock()
_clients = []        # lista de Queue, uno por cliente SSE conectado
_clients_lock = threading.Lock()


def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", LOG_PORT))
    print(f"[server] escuchando UDP en 0.0.0.0:{LOG_PORT}")
    while True:
        data, addr = sock.recvfrom(2048)
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            continue
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {text}"
        print(line)
        with _history_lock:
            _history.append(line)
            if len(_history) > MAX_HISTORY:
                _history.pop(0)
        with _clients_lock:
            for q in list(_clients):
                try:
                    q.put_nowait(line)
                except queue.Full:
                    pass


HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Logs Pico W</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: ui-monospace, Menlo, Consolas, monospace;
      background: #1e1e1e;
      color: #d4d4d4;
      margin: 0;
      padding: 0;
    }
    header {
      background: #2d2d30;
      padding: 8px 16px;
      border-bottom: 1px solid #3e3e42;
      display: flex;
      gap: 16px;
      align-items: center;
    }
    header h1 { font-size: 14px; margin: 0; font-weight: 600; }
    header .dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: #4ec9b0;
      animation: pulse 1.5s infinite;
    }
    @keyframes pulse { 0%,100% {opacity:1} 50% {opacity:.3} }
    header button {
      background: #3e3e42; color: #d4d4d4; border: 1px solid #555;
      padding: 4px 10px; font-family: inherit; cursor: pointer;
    }
    header button:hover { background: #505055; }
    #logs {
      padding: 8px 16px;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12.5px;
      line-height: 1.5;
    }
    .line { padding: 2px 0; border-bottom: 1px solid #2a2a2a; }
    .line.sep { color: #569cd6; }
    .line.warn { color: #ce9178; }
    .line.err { color: #f44747; }
    .line.ok { color: #4ec9b0; }
  </style>
</head>
<body>
  <header>
    <span class="dot" id="dot"></span>
    <h1>Logs Pico W</h1>
    <button onclick="document.getElementById('logs').innerHTML=''">Limpiar</button>
    <label><input type="checkbox" id="autoscroll" checked> Auto-scroll</label>
  </header>
  <div id="logs"></div>

<script>
  const logs = document.getElementById('logs');
  const dot = document.getElementById('dot');
  const auto = document.getElementById('autoscroll');

  function classify(text) {
    if (text.includes('---')) return 'sep';
    if (text.includes('error') || text.includes('Error') || text.includes('NO DETECTADA')) return 'err';
    if (text.includes('Acción') || text.includes('CENTRADO') || text.includes('Centro alcanzado')) return 'ok';
    if (text.includes('Obstáculo') || text.includes('esperando') || text.includes('Faltan')) return 'warn';
    return '';
  }

  const es = new EventSource('/events');
  es.onmessage = (e) => {
    const div = document.createElement('div');
    div.className = 'line ' + classify(e.data);
    div.textContent = e.data;
    logs.appendChild(div);
    if (auto.checked) window.scrollTo(0, document.body.scrollHeight);
  };
  es.onerror = () => { dot.style.background = '#f44747'; };
  es.onopen = () => { dot.style.background = '#4ec9b0'; };
</script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return  # silenciar acceso HTTP

    def do_GET(self):
        if self.path == "/":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = queue.Queue(maxsize=1000)
            with _clients_lock:
                _clients.append(q)
            try:
                with _history_lock:
                    snapshot = list(_history)
                for line in snapshot:
                    self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                self.wfile.flush()
                while True:
                    try:
                        line = q.get(timeout=15)
                        self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with _clients_lock:
                    if q in _clients:
                        _clients.remove(q)
            return

        self.send_response(404)
        self.end_headers()


class ThreadingHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    threading.Thread(target=udp_listener, daemon=True).start()
    ip = _local_ip()
    print(f"[server] HTTP en  http://localhost:{WEB_PORT}")
    print(f"[server] IP LAN: {ip}  →  pon PC_IP = \"{ip}\" en main.py de la Pico")
    server = ThreadingHTTPServer(("0.0.0.0", WEB_PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] adiós")
