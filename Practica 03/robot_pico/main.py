
import network, socket, time, os, sys, machine
from machine import Pin
from time import sleep_ms

RED_SSID            = "TU_SSID"
RED_CLAVE        = "TU_PASSWORD"
ARCHIVO_USUARIO  = "user_code.py"
ARCHIVO_BACKUP     = "user_code.bak"
BANDERA_SALTO       = "skip.flag"
PIN_MODO_SEGURO   = 22
TAM_MAX_SUBIDA = 200_000

try:
    pinModoSeguro = Pin(PIN_MODO_SEGURO, Pin.IN, Pin.PULL_UP)
    modoSeguro = (pinModoSeguro.value() == 0)
except Exception:
    modoSeguro = False

wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(RED_SSID, RED_CLAVE)

print("Recovery: conectando a WiFi '{}' ...".format(RED_SSID))
contadorWifi = 30
while not wifi.isconnected() and contadorWifi > 0:
    print(".", end="")
    time.sleep(1)
    contadorWifi -= 1
print("")

if wifi.isconnected():
    ipNodo = wifi.ifconfig()[0]
    contadorIp = 10
    while ipNodo == "0.0.0.0" and contadorIp > 0:
        time.sleep(0.5)
        ipNodo = wifi.ifconfig()[0]
        contadorIp -= 1
    time.sleep(1)
    print("Recovery: conectado. IP =", ipNodo)
else:
    ipNodo = "0.0.0.0"
    print("Recovery: NO conectado tras 30s.")
    print("  -> Revisa SSID/contraseña en main.py o que la red esté encendida.")
    print("  -> Sin WiFi, el servidor recovery no será accesible.")

def existeFichero(ruta):
    try:
        os.stat(ruta)
        return True
    except OSError:
        return False

ultimoError = None
huboFalloPrevio = existeFichero(BANDERA_SALTO)
if huboFalloPrevio:
    try: os.remove(BANDERA_SALTO)
    except OSError: pass
    print("Recovery: detectado crash en arranque anterior → saltando user_code.py.")

if modoSeguro:
    ultimoError = "Modo seguro activo (GPIO {} a LOW). user_code.py omitido a propósito.".format(PIN_MODO_SEGURO)
elif huboFalloPrevio:
    ultimoError = "Arranque anterior crasheó. user_code.py omitido para no entrar en bucle. Reinicia para volver a intentarlo."
elif not existeFichero(ARCHIVO_USUARIO):
    ultimoError = "No existe " + ARCHIVO_USUARIO + ". Sube uno desde esta interfaz."
else:
    try:
        with open(ARCHIVO_USUARIO) as fichero:
            contenidoCodigo = fichero.read()
        compile(contenidoCodigo, ARCHIVO_USUARIO, "exec")
        print("Recovery: ejecutando", ARCHIVO_USUARIO, "...")
        exec(contenidoCodigo, globals())
        ultimoError = "user_code.py terminó (no llegó a entrar en bucle infinito)."
    except KeyboardInterrupt:
        raise
    except Exception as error:
        ultimoError = "{}: {}".format(type(error).__name__, error)
        print("Recovery: user_code.py falló →", ultimoError)
        sys.print_exception(error)
        try:
            with open(BANDERA_SALTO, "w") as fichero:
                fichero.write("1")
        except Exception:
            pass
        print("Recovery: reseteando para limpiar sockets ...")
        sleep_ms(1500)
        machine.reset()

print("=== RECOVERY MODE ===")
print("Razón:", ultimoError)

try:
    from PicoAutonomousRobotics import KitronikPicoRobotBuggy
    robotRecovery = KitronikPicoRobotBuggy()
    robotRecovery.motorOn("l", "f", 0)
    robotRecovery.motorOn("r", "f", 0)
    robotRecovery.silence()
    for indiceLed in range(4):
        robotRecovery.setLED(indiceLed, (255, 0, 0))
    robotRecovery.show()
except Exception as excepcion:
    print("Recovery: no pude inicializar el buggy:", excepcion)
    robotRecovery = None

HTML_RECOVERY = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KITRONIK // RECOVERY</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #0a0408;
  --cyan: #00e5ff;
  --pink: #ff2e88;
  --red: #ff3355;
  --amber: #ffaa00;
  --green: #00ff88;
  --text: #ffd8e8;
  --dim: #886070;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.55; }
}
body {
  min-height: 100vh;
  padding: 2rem 1rem;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  color: var(--text);
  background: var(--bg);
  background-image:
    radial-gradient(ellipse 80% 50% at 50% 0%,  rgba(255,51,85,0.18), transparent 60%),
    radial-gradient(ellipse 70% 50% at 50% 100%, rgba(0,229,255,0.06), transparent 60%);
  position: relative;
  overflow-x: hidden;
}
body::before {
  content: '';
  position: fixed; inset: 0;
  background: repeating-linear-gradient(
    0deg,
    rgba(255,255,255,0.03) 0,
    rgba(255,255,255,0.03) 1px,
    transparent 1px,
    transparent 3px
  );
  pointer-events: none;
  z-index: 1;
}
.wrap { max-width: 760px; margin: 0 auto; position: relative; z-index: 2; }

.alert {
  display: inline-block;
  padding: 0.45rem 1.2rem;
  font-size: 0.75rem; font-weight: 900;
  letter-spacing: 0.3em; text-transform: uppercase;
  color: var(--bg);
  background: var(--pink);
  margin-bottom: 0.9rem;
  box-shadow: 0 0 22px rgba(255,46,136,0.7), 0 0 44px rgba(255,46,136,0.35);
  animation: pulse 1.6s ease-in-out infinite;
}

.hdr {
  border: 1px solid var(--pink);
  border-left: 4px solid var(--red);
  background: rgba(255,46,136,0.06);
  padding: 1rem 1.4rem;
  margin-bottom: 1.4rem;
  position: relative;
}
.hdr::after {
  content: ''; position: absolute; top: 0; right: 0;
  width: 18px; height: 18px;
  background: linear-gradient(135deg, transparent 50%, var(--red) 50%);
}
.hdr h1 {
  font-size: 1.5rem; font-weight: 900;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--pink);
  text-shadow: 0 0 12px rgba(255,46,136,0.65), 0 0 24px rgba(255,46,136,0.3);
  margin-bottom: 0.25rem;
}
.hdr h1 .sl { color: var(--cyan); text-shadow: 0 0 10px rgba(0,229,255,0.7); }
.hdr .sub {
  font-size: 0.72rem; color: var(--dim);
  letter-spacing: 0.22em; text-transform: uppercase;
}

.panel {
  border: 1px solid rgba(255,46,136,0.22);
  border-left: 3px solid var(--pink);
  background: rgba(14,6,12,0.65);
  padding: 1.1rem 1.3rem;
  margin-bottom: 1.1rem;
  position: relative;
}
.panel::after {
  content: ''; position: absolute; bottom: 0; right: 0;
  width: 14px; height: 14px;
  background: linear-gradient(315deg, transparent 50%, rgba(255,46,136,0.55) 50%);
}
.panel h2 {
  font-size: 0.78rem; font-weight: 700;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--pink);
  margin-bottom: 0.9rem;
  padding-bottom: 0.45rem;
  border-bottom: 1px dashed rgba(255,46,136,0.2);
}
.panel h2::before { content: '> '; color: var(--cyan); }

.diag {
  display: flex; justify-content: space-between;
  padding: 0.35rem 0;
  border-bottom: 1px dotted rgba(255,46,136,0.12);
  font-size: 0.82rem;
}
.diag:last-of-type { border-bottom: none; }
.k { color: var(--dim); letter-spacing: 0.1em; text-transform: uppercase; }
.v { color: var(--text); font-family: inherit; }

.err {
  margin-top: 0.9rem;
  padding: 0.8rem 1rem;
  background: rgba(255,51,85,0.1);
  border-left: 3px solid var(--red);
  color: #ffb0bd;
  font-family: inherit;
  font-size: 0.82rem;
  word-break: break-word;
}

.upload-zone {
  border: 1px dashed rgba(255,46,136,0.3);
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
  border: 1px solid rgba(255,46,136,0.2);
  border-left: 3px solid var(--cyan);
  color: var(--green);
  font-family: inherit; font-size: 0.82rem;
  resize: vertical; outline: none;
}
textarea:focus { border-color: var(--pink); box-shadow: 0 0 14px rgba(255,46,136,0.3); }

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
.act-up   { color: var(--cyan); border-color: var(--cyan); }
.act-up:hover { background: rgba(0,229,255,0.1); box-shadow: 0 0 16px rgba(0,229,255,0.45); }
.act-go   { color: var(--green); border-color: var(--green); }
.act-go:hover { background: rgba(0,255,136,0.1); box-shadow: 0 0 16px rgba(0,255,136,0.45); }
.act-warn { color: var(--amber); border-color: var(--amber); }
.act-warn:hover { background: rgba(255,170,0,0.1); box-shadow: 0 0 16px rgba(255,170,0,0.45); }
.act-bad  { color: var(--red); border-color: var(--red); }
.act-bad:hover { background: rgba(255,51,85,0.1); box-shadow: 0 0 16px rgba(255,51,85,0.45); }
.act-mut  { color: var(--dim); border-color: var(--dim); }
.act-mut:hover { color: var(--pink); border-color: var(--pink); box-shadow: 0 0 14px rgba(255,46,136,0.3); }

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
</style>
</head>
<body>
  <div class="wrap">

    <div class="alert">&#x26A0; SYSTEM HALTED &middot; RECOVERY MODE</div>

    <div class="hdr">
      <h1>Kitronik <span class="sl">//</span> Recovery</h1>
      <div class="sub">El bucle principal no se está ejecutando &middot; Motores parados</div>
    </div>

    <div class="panel">
      <h2>Diagnóstico</h2>
      <div class="diag"><span class="k">IP</span><span class="v">__IP__</span></div>
      <div class="diag"><span class="k">SSID</span><span class="v">__SSID__</span></div>
      <div class="diag"><span class="k">user_code.py</span><span class="v">__UC__</span></div>
      <div class="diag"><span class="k">backup</span><span class="v">__BK__</span></div>
      <div class="diag"><span class="k">Pin recovery</span><span class="v">GPIO __SAFE__ a LOW</span></div>
      <div class="diag"><span class="k">Motores</span><span class="v">__MOT__</span></div>
      <div class="err">__ERR__</div>
    </div>

    <div class="panel">
      <h2>Subir nuevo user_code.py</h2>
      <div class="upload-zone">
        <input type="file" id="codefile" accept=".py,text/plain">
        <p>// o pega el código abajo</p>
      </div>
      <textarea id="codetext" placeholder="# Pega aquí tu código Python..."></textarea>
      <div class="actions">
        <button class="act act-up"  onclick="upload()">Subir y reiniciar</button>
        <button class="act act-mut" onclick="document.getElementById('codetext').value=''; document.getElementById('codefile').value='';">Limpiar</button>
      </div>
      <div id="result"></div>
    </div>

    <div class="panel">
      <h2>Acciones</h2>
      <div class="actions">
        <button class="act act-go"   onclick="location.href='/reset'">Reiniciar</button>
        <button class="act act-warn" onclick="if(confirm('Restaurar user_code.bak sobre user_code.py?')) location.href='/restore'">Restaurar backup</button>
        <button class="act act-bad"  onclick="if(confirm('Borrar user_code.py?')) location.href='/delete'">Borrar user_code.py</button>
      </div>
    </div>

    <div class="footer">RECOVERY SERVER v1 &middot; PRÁCTICA 3 SEU &middot; KITRONIK BUGGY</div>
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

servidor = None
for intento in range(3):
    try:
        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind(("", 80))
        servidor.listen(2)
        break
    except OSError as excepcion:
        print("Recovery: bind puerto 80 falló (intento {}/3): {}".format(intento + 1, excepcion))
        try:
            if servidor is not None: servidor.close()
        except Exception:
            pass
        servidor = None
        if intento == 0:
            try:
                with open(BANDERA_SALTO, "w") as fichero:
                    fichero.write("1")
            except Exception:
                pass
            print("Recovery: reseteando para liberar el puerto ...")
            sleep_ms(1500)
            machine.reset()
        sleep_ms(1000)

if servidor is None:
    print("Recovery: imposible abrir puerto 80 tras 3 intentos. Reset manual necesario.")
    while True:
        sleep_ms(1000)

print("Recovery: HTTP en http://{}".format(ipNodo))


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


def construirPagina():
    textoMotor = '<span style="color:#00ff88;">STOP (rojo)</span>' if robotRecovery else '<span style="color:#886070;">n/a</span>'
    textoError = (ultimoError or "—").replace("<", "&lt;").replace(">", "&gt;")
    return HTML_RECOVERY \
        .replace("__IP__",   ipNodo) \
        .replace("__SSID__", RED_SSID) \
        .replace("__UC__",   "presente" if existeFichero(ARCHIVO_USUARIO) else "ausente") \
        .replace("__BK__",   "presente" if existeFichero(ARCHIVO_BACKUP)   else "ausente") \
        .replace("__SAFE__", str(PIN_MODO_SEGURO)) \
        .replace("__MOT__",  textoMotor) \
        .replace("__ERR__",  textoError)


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
        return responder(conexion, "Fichero > {} bytes (límite).".format(TAM_MAX_SUBIDA), "413 Payload Too Large")

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
        return responder(conexion, "Cuerpo incompleto ({}/{} bytes).".format(len(cuerpo), longitudContenido), "400 Bad Request")

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
            print("Recovery: no pude crear backup:", error)

    try:
        with open(ARCHIVO_USUARIO, "w") as fichero:
            fichero.write(codigoFuente)
    except Exception as error:
        return responder(conexion, "Error guardando: {}".format(error), "500 Internal Server Error")

    responder(conexion, "OK: {} bytes guardados en {}. Reiniciando...".format(len(codigoFuente), ARCHIVO_USUARIO))


print("Recovery: esperando peticiones...")
while True:
    try:
        conexion, direccion = servidor.accept()
    except Exception as error:
        print("Recovery accept:", error)
        sleep_ms(200)
        continue

    try:
        conexion.settimeout(2.0)
        try:
            datosCrudos = conexion.recv(4096)
        except Exception:
            conexion.close()
            continue
        if not datosCrudos:
            conexion.close()
            continue

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
            conexion.close()
            continue

        primeraLinea = peticion.split("\r\n", 1)[0]

        if primeraLinea.startswith("POST /upload"):
            procesarSubida(conexion, peticion, bytesCuerpo)

        elif primeraLinea.startswith("GET /reset"):
            responder(conexion, "Reiniciando...")
            try: conexion.close()
            except Exception: pass
            sleep_ms(500)
            machine.reset()

        elif primeraLinea.startswith("GET /delete"):
            try:
                os.remove(ARCHIVO_USUARIO)
            except OSError:
                pass
            responderRedireccion(conexion)

        elif primeraLinea.startswith("GET /restore"):
            if existeFichero(ARCHIVO_BACKUP):
                try:
                    with open(ARCHIVO_BACKUP) as ficheroOrigen, open(ARCHIVO_USUARIO, "w") as ficheroDestino:
                        ficheroDestino.write(ficheroOrigen.read())
                    responder(conexion, "Backup restaurado en user_code.py. Pulsa Reiniciar.")
                except Exception as error:
                    responder(conexion, "Error restaurando: {}".format(error), "500 Internal Server Error")
            else:
                responder(conexion, "No hay backup disponible.", "404 Not Found")

        else:
            responder(conexion, construirPagina(), tipoContenido="text/html; charset=utf-8")

    except Exception as error:
        print("Recovery handler:", error)
        try:
            responder(conexion, "Error servidor: {}".format(error), "500 Internal Server Error")
        except Exception:
            pass
    finally:
        try:
            conexion.close()
        except Exception:
            pass
