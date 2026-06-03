
import network
import socket
import os
import machine
from time import sleep_ms, ticks_ms, ticks_diff
from PicoAutonomousRobotics import KitronikPicoRobotBuggy

ARCHIVO_USUARIO  = "user_code.py"
ARCHIVO_BACKUP     = "user_code.bak"
TAM_MAX_SUBIDA = 200_000

wifi = network.WLAN(network.STA_IF)
if not wifi.isconnected():
    raise RuntimeError("WiFi no conectado. Arranca este fichero desde main.py.")
ipNodo = wifi.ifconfig()[0]
print("user_code.py: WiFi ya activo, IP =", ipNodo)

robot = KitronikPicoRobotBuggy()

COLOR_APAGADO    = (0, 0, 0)
COLOR_AMBAR = (255, 150, 0)

LEDS_IZQUIERDA  = (0, 3)
LEDS_DERECHA = (1, 2)

DIST_OBSTACULO_CM       = 20
ADEL_CURVA_MS = 450
ADEL_RECTO_MS  = 1000
CURVA_LENTA = 15
CURVA_RAPIDA = 30
CRUCERO     = 25

modo       = "STOPPED"
cronoParpadeo = ticks_ms()
parpadeoActivo = False

faseAdelantamiento = None
cronoAdelantamiento = 0

for indiceLed in range(4):
    robot.setLED(indiceLed, COLOR_APAGADO)
robot.show()

PAGINA_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>KITRONIK // CONTROL</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #04040c;
      --cyan: #00e5ff;
      --pink: #ff2e88;
      --amber: #ffaa00;
      --green: #00ff88;
      --red: #ff3355;
      --text: #d8dcff;
      --dim: #6c7a99;
    }
    @keyframes pulse-red {
      0%, 100% { box-shadow: 0 0 18px rgba(255,51,85,0.55), inset 0 0 18px rgba(255,51,85,0.18); }
      50%      { box-shadow: 0 0 32px rgba(255,51,85,0.95), inset 0 0 28px rgba(255,51,85,0.32); }
    }
    body {
      min-height: 100vh;
      padding: 2rem 1rem;
      font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
      color: var(--text);
      background: var(--bg);
      background-image:
        radial-gradient(ellipse 70% 50% at 20% 0%,  rgba(255,46,136,0.10), transparent 60%),
        radial-gradient(ellipse 70% 50% at 80% 100%, rgba(0,229,255,0.10), transparent 60%);
      position: relative;
      overflow-x: hidden;
    }
    body::before {
      content: '';
      position: fixed; inset: 0;
      background: repeating-linear-gradient(
        0deg,
        rgba(255,255,255,0.025) 0,
        rgba(255,255,255,0.025) 1px,
        transparent 1px,
        transparent 3px
      );
      pointer-events: none;
      z-index: 1;
    }
    .wrap { max-width: 760px; margin: 0 auto; position: relative; z-index: 2; }

    .hdr {
      border: 1px solid var(--cyan);
      border-left: 4px solid var(--pink);
      background: rgba(0,229,255,0.04);
      padding: 1rem 1.4rem;
      margin-bottom: 1.4rem;
      position: relative;
    }
    .hdr::after {
      content: ''; position: absolute; top: 0; right: 0;
      width: 18px; height: 18px;
      background: linear-gradient(135deg, transparent 50%, var(--pink) 50%);
    }
    .hdr h1 {
      font-size: 1.5rem; font-weight: 900;
      letter-spacing: 0.18em; text-transform: uppercase;
      color: var(--cyan);
      text-shadow: 0 0 12px rgba(0,229,255,0.55), 0 0 22px rgba(0,229,255,0.25);
      margin-bottom: 0.25rem;
    }
    .hdr h1 .sl { color: var(--pink); text-shadow: 0 0 10px rgba(255,46,136,0.7); }
    .hdr .sub {
      font-size: 0.72rem; color: var(--dim);
      letter-spacing: 0.22em; text-transform: uppercase;
    }
    .badge {
      display: inline-block; margin-top: 0.7rem;
      padding: 0.25rem 0.9rem;
      font-size: 0.74rem; font-weight: 700;
      letter-spacing: 0.22em; text-transform: uppercase;
      color: var(--pink);
      background: rgba(255,46,136,0.07);
      border: 1px solid var(--pink);
      box-shadow: inset 0 0 14px rgba(255,46,136,0.18), 0 0 12px rgba(255,46,136,0.25);
    }

    .panel {
      border: 1px solid rgba(0,229,255,0.22);
      border-left: 3px solid var(--cyan);
      background: rgba(8,10,22,0.65);
      padding: 1.1rem 1.3rem;
      margin-bottom: 1.1rem;
      position: relative;
    }
    .panel::after {
      content: ''; position: absolute; bottom: 0; right: 0;
      width: 14px; height: 14px;
      background: linear-gradient(315deg, transparent 50%, rgba(0,229,255,0.55) 50%);
    }
    .panel h2 {
      font-size: 0.78rem; font-weight: 700;
      letter-spacing: 0.22em; text-transform: uppercase;
      color: var(--cyan);
      margin-bottom: 0.9rem;
      padding-bottom: 0.45rem;
      border-bottom: 1px dashed rgba(0,229,255,0.18);
    }
    .panel h2::before { content: '> '; color: var(--pink); }

    .ctrl-grid { display: flex; gap: 1rem; flex-wrap: wrap; justify-content: center; }
    .ctrl {
      width: 150px; height: 150px;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: 0.5rem; text-decoration: none;
      font-size: 0.82rem; font-weight: 700;
      letter-spacing: 0.18em; text-transform: uppercase;
      background: rgba(8,10,22,0.85);
      border: 1px solid;
      clip-path: polygon(14px 0, 100% 0, 100% calc(100% - 14px), calc(100% - 14px) 100%, 0 100%, 0 14px);
      transition: transform 0.15s, box-shadow 0.15s;
    }
    .ctrl svg { width: 40px; height: 40px; }
    .ctrl:hover { transform: translateY(-3px); }
    .ctrl-fwd { color: var(--cyan); border-color: var(--cyan); }
    .ctrl-fwd:hover { box-shadow: 0 0 20px rgba(0,229,255,0.55), inset 0 0 18px rgba(0,229,255,0.12); }
    .ctrl-fwd svg { fill: var(--cyan); }
    .ctrl-bwd { color: var(--pink); border-color: var(--pink); }
    .ctrl-bwd:hover { box-shadow: 0 0 20px rgba(255,46,136,0.55), inset 0 0 18px rgba(255,46,136,0.12); }
    .ctrl-bwd svg { fill: var(--pink); }
    .ctrl-stp { color: var(--amber); border-color: var(--amber); }
    .ctrl-stp:hover { box-shadow: 0 0 20px rgba(255,170,0,0.55), inset 0 0 18px rgba(255,170,0,0.12); }
    .ctrl-stp svg { fill: var(--amber); }

    .upload-zone {
      border: 1px dashed rgba(0,229,255,0.3);
      padding: 0.9rem; text-align: center;
      margin-bottom: 0.7rem;
      background: rgba(0,0,0,0.3);
    }
    .upload-zone p {
      color: var(--dim); font-size: 0.72rem;
      margin-top: 0.5rem; letter-spacing: 0.1em;
    }
    input[type=file] { color: var(--dim); font-family: inherit; font-size: 0.8rem; }
    textarea {
      width: 100%; min-height: 140px; padding: 0.8rem;
      background: rgba(0,0,0,0.55);
      border: 1px solid rgba(0,229,255,0.2);
      border-left: 3px solid var(--pink);
      color: var(--green);
      font-family: inherit; font-size: 0.82rem;
      resize: vertical; outline: none;
    }
    textarea:focus { border-color: var(--cyan); box-shadow: 0 0 14px rgba(0,229,255,0.3); }

    .actions { display: flex; gap: 0.6rem; flex-wrap: wrap; margin-top: 0.8rem; }
    .act {
      flex: 1; min-width: 140px;
      padding: 0.7rem 1rem;
      background: transparent;
      border: 1px solid;
      cursor: pointer;
      font-family: inherit; font-size: 0.78rem; font-weight: 700;
      letter-spacing: 0.18em; text-transform: uppercase;
      transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
    }
    .act:hover { transform: translateY(-2px); }
    .act-up   { color: var(--pink); border-color: var(--pink); }
    .act-up:hover { background: rgba(255,46,136,0.1); box-shadow: 0 0 16px rgba(255,46,136,0.45); }
    .act-go   { color: var(--green); border-color: var(--green); }
    .act-go:hover { background: rgba(0,255,136,0.1); box-shadow: 0 0 16px rgba(0,255,136,0.45); }
    .act-mut  { color: var(--dim); border-color: var(--dim); }
    .act-mut:hover { color: var(--cyan); border-color: var(--cyan); box-shadow: 0 0 14px rgba(0,229,255,0.3); }

    .hotfix-panel {
      border: 1px solid var(--red);
      border-left: 4px solid var(--red);
      background:
        linear-gradient(135deg, rgba(255,51,85,0.10), rgba(255,46,136,0.06)),
        rgba(8,10,22,0.7);
      padding: 1.4rem 1.3rem;
      margin-bottom: 1.1rem;
      position: relative;
      animation: pulse-red 2.4s ease-in-out infinite;
    }
    .hotfix-panel::after {
      content: ''; position: absolute; bottom: 0; right: 0;
      width: 16px; height: 16px;
      background: linear-gradient(315deg, transparent 50%, var(--red) 50%);
    }
    .hotfix-panel h2 {
      font-size: 0.78rem; font-weight: 700;
      letter-spacing: 0.22em; text-transform: uppercase;
      color: var(--red);
      margin-bottom: 0.9rem;
      padding-bottom: 0.45rem;
      border-bottom: 1px dashed rgba(255,51,85,0.3);
    }
    .hotfix-panel h2::before { content: '> '; color: var(--amber); }
    .hotfix-btn {
      display: block;
      width: 100%;
      padding: 1.3rem 1rem;
      background: linear-gradient(135deg, rgba(255,51,85,0.18), rgba(255,46,136,0.10));
      border: 2px solid var(--red);
      cursor: pointer;
      font-family: inherit;
      font-size: 1.15rem; font-weight: 900;
      letter-spacing: 0.32em; text-transform: uppercase;
      color: var(--red);
      text-shadow: 0 0 10px rgba(255,51,85,0.6), 0 0 18px rgba(255,51,85,0.3);
      transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
    }
    .hotfix-btn::before { content: '\\26A0  '; color: var(--amber); margin-right: 0.4em; }
    .hotfix-btn::after  { content: '  \\26A0'; color: var(--amber); margin-left: 0.4em; }
    .hotfix-btn:hover {
      transform: translateY(-3px);
      background: linear-gradient(135deg, rgba(255,51,85,0.32), rgba(255,46,136,0.20));
      box-shadow: 0 0 28px rgba(255,51,85,0.7), inset 0 0 22px rgba(255,51,85,0.25);
    }
    .hotfix-btn:active { transform: scale(0.98); }
    .hotfix-hint {
      margin-top: 0.7rem;
      font-size: 0.72rem;
      color: var(--dim);
      letter-spacing: 0.12em;
      text-transform: uppercase;
      text-align: center;
    }

    #result {
      margin-top: 0.8rem; padding: 0.7rem;
      border-left: 3px solid;
      font-family: inherit; font-size: 0.82rem;
      display: none; word-break: break-word;
    }
    .ok  { color: var(--green); border-color: var(--green); background: rgba(0,255,136,0.05); }
    .bad { color: var(--red);   border-color: var(--red);   background: rgba(255,51,85,0.05); }

    .footer {
      text-align: center;
      color: var(--dim);
      font-size: 0.7rem;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      margin-top: 1rem;
    }
    .footer .ip { color: var(--cyan); }
  </style>
</head>
<body>
  <div class="wrap">

    <div class="hdr">
      <h1>Kitronik <span class="sl">//</span> Control</h1>
      <div class="sub">Sistemas Empotrados y Ubicuos &middot; NODE.ONLINE</div>
      <div class="badge">STATE :: STATE_PLACEHOLDER</div>
    </div>

    <div class="panel">
      <h2>Motion Control</h2>
      <div class="ctrl-grid">
        <a href="/forward" class="ctrl ctrl-fwd">
          <svg viewBox="0 0 24 24"><path d="M12 2l8 8h-5v12H9V10H4z"/></svg>
          Adelante
        </a>
        <a href="/backward" class="ctrl ctrl-bwd">
          <svg viewBox="0 0 24 24"><path d="M12 22l-8-8h5V2h6v12h5z"/></svg>
          Atr&aacute;s
        </a>
        <a href="/stopped" class="ctrl ctrl-stp">
          <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          Averiado
        </a>
      </div>
    </div>

    <div class="panel">
      <h2>Upload user_code.py</h2>
      <div class="upload-zone">
        <input type="file" id="codefile" accept=".py,text/plain">
        <p>// o pega el código abajo</p>
      </div>
      <textarea id="codetext" placeholder="# Pega aqu&iacute; tu c&oacute;digo Python..."></textarea>
      <div class="actions">
        <button class="act act-up"  onclick="upload()">Subir y reiniciar</button>
        <button class="act act-mut" onclick="document.getElementById('codetext').value=''; document.getElementById('codefile').value='';">Limpiar</button>
      </div>
      <div id="result"></div>
    </div>

    <div class="panel">
      <h2>System</h2>
      <div class="actions">
        <button class="act act-go" onclick="location.href='/reset'">Reiniciar</button>
      </div>
    </div>

    <div class="hotfix-panel">
      <h2>Emergency Hotfix</h2>
      <button class="hotfix-btn" onclick="if(confirm('Forzar modo recovery (borra user_code.py)?')) location.href='/go-recovery'">Reparaci&oacute;n en Caliente</button>
      <p class="hotfix-hint">// borra user_code.py y arranca en modo recovery</p>
    </div>

    <div class="footer">NODE_IP :: <span class="ip">IP_PLACEHOLDER</span></div>
  </div>

<script>
async function upload() {
  const f = document.getElementById('codefile');
  const t = document.getElementById('codetext');
  const r = document.getElementById('result');
  let code = '';
  if (f.files.length > 0)              code = await f.files[0].text();
  else if (t.value.trim().length > 0)  code = t.value;
  else {
    r.style.display = 'block'; r.className = 'bad';
    r.textContent = 'Selecciona un fichero o pega código.'; return;
  }
  r.style.display = 'block'; r.className = '';
  r.textContent = 'Subiendo (' + code.length + ' bytes)...';
  try {
    const res = await fetch('/upload', {
      method: 'POST',
      headers: {'Content-Type': 'text/plain; charset=utf-8'},
      body: code
    });
    const msg = await res.text();
    r.className = res.ok ? 'ok' : 'bad';
    r.textContent = msg;
    if (res.ok) setTimeout(() => location.href = '/reset', 1500);
  } catch (e) {
    r.className = 'bad'; r.textContent = 'Error de red: ' + e;
  }
}
</script>
</body>
</html>
"""

socketServidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socketServidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
socketServidor.bind(("", 80))
socketServidor.listen(1)
socketServidor.setblocking(False)

print("Servidor HTTP escuchando en http://{}".format(ipNodo))


def existeFichero(ruta):
    try:
        os.stat(ruta)
        return True
    except OSError:
        return False


def enviarTodo(conexion, data):
    vista = memoryview(data)
    totalBytes = len(data)
    enviados = 0
    while enviados < totalBytes:
        try:
            bytesEnviados = conexion.send(vista[enviados:])
        except OSError:
            return
        if bytesEnviados is None or bytesEnviados <= 0:
            return
        enviados += bytesEnviados


def responderRedireccion(conexion, destino="/"):
    cabecera = "HTTP/1.1 302 Found\r\nLocation: {}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".format(destino)
    enviarTodo(conexion, cabecera.encode("utf-8"))


def responder(conexion, cuerpo, estadoHttp="200 OK", tipoContenido="text/plain; charset=utf-8"):
    if isinstance(cuerpo, str):
        cuerpo = cuerpo.encode("utf-8")
    cabecera = "HTTP/1.1 {}\r\nContent-Type: {}\r\nConnection: close\r\nContent-Length: {}\r\n\r\n".format(
        estadoHttp, tipoContenido, len(cuerpo)
    )
    enviarTodo(conexion, cabecera.encode("utf-8"))
    enviarTodo(conexion, cuerpo)


def procesarSubida(conexion, cabecerasPeticion, cuerpoInicial):
    longitudContenido = 0
    for lineaCab in cabecerasPeticion.split("\r\n"):
        if lineaCab.lower().startswith("content-length:"):
            try:
                longitudContenido = int(lineaCab.split(":", 1)[1].strip())
            except ValueError:
                longitudContenido = 0
            break
    if longitudContenido <= 0:
        return responder(conexion, "Falta Content-Length o es inválido.", "400 Bad Request")
    if longitudContenido > TAM_MAX_SUBIDA:
        return responder(conexion, "Fichero > {} bytes.".format(TAM_MAX_SUBIDA), "413 Payload Too Large")

    cuerpo = cuerpoInicial
    conexion.settimeout(3.0)
    while len(cuerpo) < longitudContenido:
        try:
            fragmento = conexion.recv(min(2048, longitudContenido - len(cuerpo)))
        except Exception:
            break
        if not fragmento:
            break
        cuerpo += fragmento
    if len(cuerpo) < longitudContenido:
        return responder(conexion, "Cuerpo incompleto ({}/{}).".format(len(cuerpo), longitudContenido), "400 Bad Request")

    try:
        codigoFuente = cuerpo.decode("utf-8")
    except UnicodeError:
        return responder(conexion, "El fichero debe estar en UTF-8.", "400 Bad Request")

    try:
        compile(codigoFuente, ARCHIVO_USUARIO, "exec")
    except SyntaxError as error:
        return responder(conexion, "SyntaxError: {}".format(error), "400 Bad Request")
    except Exception as error:
        return responder(conexion, "Error compilando: {}".format(error), "400 Bad Request")

    if existeFichero(ARCHIVO_USUARIO):
        try:
            with open(ARCHIVO_USUARIO) as ficheroAntiguo, open(ARCHIVO_BACKUP, "w") as ficheroNuevo:
                ficheroNuevo.write(ficheroAntiguo.read())
        except Exception as error:
            print("No pude crear backup:", error)

    try:
        with open(ARCHIVO_USUARIO, "w") as fichero:
            fichero.write(codigoFuente)
    except Exception as error:
        return responder(conexion, "Error guardando: {}".format(error), "500 Internal Server Error")

    responder(conexion, "OK: {} bytes guardados en {}. Reiniciando...".format(len(codigoFuente), ARCHIVO_USUARIO))


def actualizarParpadeo():
    global cronoParpadeo, parpadeoActivo
    if ticks_diff(ticks_ms(), cronoParpadeo) > 300:
        parpadeoActivo = not parpadeoActivo
        cronoParpadeo = ticks_ms()


def atenderWeb():
    global modo, faseAdelantamiento
    try:
        conexion, direccion = socketServidor.accept()
    except OSError:
        return

    try:
        conexion.settimeout(0.8)
        try:
            datosCrudos = conexion.recv(4096)
        except Exception:
            conexion.close(); return
        if not datosCrudos:
            conexion.close(); return

        try:
            separador = datosCrudos.index(b"\r\n\r\n")
            bytesCabecera = datosCrudos[:separador]
            bytesCuerpo = datosCrudos[separador + 4:]
        except ValueError:
            bytesCabecera = datosCrudos
            bytesCuerpo = b""

        try:
            peticion = bytesCabecera.decode("utf-8")
        except UnicodeError:
            conexion.close(); return

        primeraLinea = peticion.split("\r\n", 1)[0]

        if primeraLinea.startswith("POST /upload"):
            procesarSubida(conexion, peticion, bytesCuerpo)

        elif primeraLinea.startswith("GET /forward"):
            modo = "FORWARD"
            responderRedireccion(conexion)

        elif primeraLinea.startswith("GET /backward"):
            modo = "BACKWARD"
            faseAdelantamiento = None
            responderRedireccion(conexion)

        elif primeraLinea.startswith("GET /stopped"):
            modo = "STOPPED"
            faseAdelantamiento = None
            responderRedireccion(conexion)

        elif primeraLinea.startswith("GET /reset"):
            responder(conexion, "Reiniciando...")
            try: conexion.close()
            except Exception: pass
            sleep_ms(500)
            machine.reset()

        elif primeraLinea.startswith("GET /restore"):
            if existeFichero(ARCHIVO_BACKUP):
                try:
                    with open(ARCHIVO_BACKUP) as ficheroOrigen, open(ARCHIVO_USUARIO, "w") as ficheroDestino:
                        ficheroDestino.write(ficheroOrigen.read())
                    responder(conexion, "Backup restaurado. Pulsa Reiniciar.")
                except Exception as error:
                    responder(conexion, "Error restaurando: {}".format(error), "500 Internal Server Error")
            else:
                responder(conexion, "No hay backup disponible.", "404 Not Found")

        elif primeraLinea.startswith("GET /go-recovery"):
            try:
                os.remove(ARCHIVO_USUARIO)
            except OSError:
                pass
            responder(conexion, "Entrando en recovery...")
            try: conexion.close()
            except Exception: pass
            sleep_ms(500)
            machine.reset()

        else:
            pagina = PAGINA_HTML.replace("STATE_PLACEHOLDER", modo) \
                            .replace("IP_PLACEHOLDER", ipNodo)
            responder(conexion, pagina, tipoContenido="text/html; charset=utf-8")

    except Exception as error:
        print("handle_web:", error)
    finally:
        try: conexion.close()
        except Exception: pass


while True:
    actualizarParpadeo()
    atenderWeb()

    if modo == "BACKWARD" and parpadeoActivo:
        robot.soundFrequency(1000)
    else:
        robot.silence()

    if modo == "FORWARD" and faseAdelantamiento is None:
        distancia = robot.getDistance("f")
        if 0 < distancia < DIST_OBSTACULO_CM:
            faseAdelantamiento = "LEFT_OUT"
            cronoAdelantamiento = ticks_ms()

    if faseAdelantamiento is not None:
        transcurrido = ticks_diff(ticks_ms(), cronoAdelantamiento)
        colorSenal  = COLOR_AMBAR if parpadeoActivo else COLOR_APAGADO

        if faseAdelantamiento == "LEFT_OUT":
            robot.motorOn("l", "f", CURVA_LENTA)
            robot.motorOn("r", "f", CURVA_RAPIDA)
            for indiceLed in LEDS_IZQUIERDA:  robot.setLED(indiceLed, colorSenal)
            for indiceLed in LEDS_DERECHA: robot.setLED(indiceLed, COLOR_APAGADO)
            if transcurrido > ADEL_CURVA_MS:
                faseAdelantamiento = "RIGHT_LEVEL"
                cronoAdelantamiento = ticks_ms()

        elif faseAdelantamiento == "RIGHT_LEVEL":
            robot.motorOn("l", "f", CURVA_RAPIDA)
            robot.motorOn("r", "f", CURVA_LENTA)
            for indiceLed in LEDS_IZQUIERDA:  robot.setLED(indiceLed, colorSenal)
            for indiceLed in LEDS_DERECHA: robot.setLED(indiceLed, COLOR_APAGADO)
            if transcurrido > ADEL_CURVA_MS:
                faseAdelantamiento = "PASS"
                cronoAdelantamiento = ticks_ms()

        elif faseAdelantamiento == "PASS":
            robot.motorOn("l", "f", CRUCERO)
            robot.motorOn("r", "f", CRUCERO)
            for indiceLed in range(4): robot.setLED(indiceLed, COLOR_APAGADO)
            if transcurrido > ADEL_RECTO_MS:
                faseAdelantamiento = "RIGHT_IN"
                cronoAdelantamiento = ticks_ms()

        elif faseAdelantamiento == "RIGHT_IN":
            robot.motorOn("l", "f", CURVA_RAPIDA)
            robot.motorOn("r", "f", CURVA_LENTA)
            for indiceLed in LEDS_DERECHA: robot.setLED(indiceLed, colorSenal)
            for indiceLed in LEDS_IZQUIERDA:  robot.setLED(indiceLed, COLOR_APAGADO)
            if transcurrido > ADEL_CURVA_MS:
                faseAdelantamiento = "LEFT_LEVEL"
                cronoAdelantamiento = ticks_ms()

        elif faseAdelantamiento == "LEFT_LEVEL":
            robot.motorOn("l", "f", CURVA_LENTA)
            robot.motorOn("r", "f", CURVA_RAPIDA)
            for indiceLed in LEDS_DERECHA: robot.setLED(indiceLed, colorSenal)
            for indiceLed in LEDS_IZQUIERDA:  robot.setLED(indiceLed, COLOR_APAGADO)
            if transcurrido > ADEL_CURVA_MS:
                faseAdelantamiento = None

    elif modo == "STOPPED":
        robot.motorOn("l", "f", 0)
        robot.motorOn("r", "f", 0)
        if parpadeoActivo:
            for indiceLed in range(4):
                robot.setLED(indiceLed, COLOR_AMBAR)
        else:
            for indiceLed in range(4):
                robot.setLED(indiceLed, COLOR_APAGADO)

    elif modo == "FORWARD":
        robot.motorOn("l", "f", 20)
        robot.motorOn("r", "f", 20)
        for indiceLed in range(4):
            robot.setLED(indiceLed, COLOR_APAGADO)

    elif modo == "BACKWARD":
        robot.motorOn("l", "r", 20)
        robot.motorOn("r", "r", 20)
        for indiceLed in range(4):
            robot.setLED(indiceLed, COLOR_APAGADO)

    robot.show()
    sleep_ms(20)
