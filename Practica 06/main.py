import bluetooth
import time
import math
import network
import socket as _socket
from PicoAutonomousRobotics import KitronikPicoRobotBuggy

WIFI_SSID = "TU_SSID"
WIFI_PASS = "TU_PASSWORD"
PC_IP     = "192.168.7.11"
LOG_PORT  = 9999
WIFI_TIMEOUT_S = 10

_wifi_ok = False
_log_sock = None
_real_print = print

def _conectar_wifi():
    global _wifi_ok, _log_sock
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            wlan.connect(WIFI_SSID, WIFI_PASS)
            t0 = time.ticks_ms()
            while not wlan.isconnected():
                if time.ticks_diff(time.ticks_ms(), t0) > WIFI_TIMEOUT_S * 1000:
                    _real_print("[WiFi] timeout — sigo solo en local")
                    return
                time.sleep_ms(200)
        ip = wlan.ifconfig()[0]
        _real_print(f"[WiFi] conectado, IP={ip}, logs → {PC_IP}:{LOG_PORT}")
        _log_sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        _wifi_ok = True
    except Exception as e:
        _real_print(f"[WiFi] error: {e}")

def log(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    _real_print(msg, **kwargs)
    if _wifi_ok and _log_sock:
        try:
            _log_sock.sendto(msg.encode("utf-8")[:1400], (PC_IP, LOG_PORT))
        except Exception:
            pass

print = log

_conectar_wifi()

buggy = KitronikPicoRobotBuggy()

LADO_CUADRADO_M = 2.5

COORDS = {
    "Baliza Inf-Izquierda": (0.0,            0.0),
    "Baliza Inf-Derecha":   (LADO_CUADRADO_M, 0.0),
    "Baliza Sup-Izquierda": (0.0,            LADO_CUADRADO_M),
    "Baliza Sup-Derecha":   (LADO_CUADRADO_M, LADO_CUADRADO_M),
}
CENTRO = (LADO_CUADRADO_M / 2, LADO_CUADRADO_M / 2)

A_REF = -62.0
N_PATH_LOSS = 3.5

VELOCIDAD = 30
TIEMPO_AVANCE_MS = 500
TIEMPO_GIRO_45_MS = 250
TIEMPO_GIRO_90_MS = 500
TIEMPO_GIRO_180_MS = 1000
TOLERANCIA_CENTRO_M = 0.5
UMBRAL_SPREAD_RSSI = 7.0
CONFIRMACIONES_CENTRO = 4
DISTANCIA_SEGURIDAD_CM = 15
DURACION_SCAN_MS = 3000
DEBUG_BLE = False

POS_FILTER_ALPHA = 0.3
DELTA_MEJORA = 0.3
DELTA_EMPEORA = 0.4
MAX_INTENTOS_ALEJANDOSE = 2

COLOR_OFF    = (0, 0, 0)
COLOR_GREEN  = (0, 255, 0)
COLOR_YELLOW = (255, 150, 0)
COLOR_RED    = (255, 0, 0)
COLOR_BLUE   = (0, 0, 255)
COLOR_PURPLE = (180, 0, 255)

BALIZAS = list(COORDS.keys())

def adelante():
    buggy.motorOn("l", "f", VELOCIDAD)
    buggy.motorOn("r", "f", VELOCIDAD)

def atras():
    buggy.motorOn("l", "r", VELOCIDAD)
    buggy.motorOn("r", "r", VELOCIDAD)

def girar_derecha():
    buggy.motorOn("l", "f", VELOCIDAD)
    buggy.motorOn("r", "r", VELOCIDAD)

def girar_izquierda():
    buggy.motorOn("l", "r", VELOCIDAD)
    buggy.motorOn("r", "f", VELOCIDAD)

def parar():
    buggy.motorOff("l")
    buggy.motorOff("r")

def set_leds(color):
    for i in range(4):
        buggy.setLED(i, color)
    buggy.show()

def hay_obstaculo_frontal():
    d = buggy.getDistance("f")
    return 0 < d <= DISTANCIA_SEGURIDAD_CM

def _decode_name(adv_data):
    i = 0
    while i < len(adv_data):
        length = adv_data[i]
        if length == 0:
            break
        type_ = adv_data[i + 1]
        if type_ in (0x08, 0x09):
            try:
                return bytes(adv_data[i + 2:i + 1 + length]).decode("utf-8")
            except:
                return None
        i += 1 + length
    return None

def escanear_balizas(duracion_ms=DURACION_SCAN_MS):
    encontrados = {}
    vistos_debug = {}

    bt = bluetooth.BLE()
    bt.active(True)

    def callback(event, data):
        if event == 5:
            addr_type, addr, adv_type, rssi, adv_data = data
            nombre = _decode_name(adv_data)
            if DEBUG_BLE and nombre:
                vistos_debug[nombre] = rssi
            if nombre and nombre in COORDS:
                encontrados.setdefault(nombre, []).append(rssi)

    bt.irq(callback)
    bt.gap_scan(duracion_ms, 30000, 30000, True)
    time.sleep_ms(duracion_ms + 200)
    bt.gap_scan(None)

    if DEBUG_BLE:
        print(f"  [DEBUG] dispositivos con nombre: {len(vistos_debug)}")
        for n, r in vistos_debug.items():
            print(f"    · '{n}' (RSSI {r} dBm)")

    rssi_promedio = {}
    for nombre in BALIZAS:
        valores = encontrados.get(nombre, [])
        if valores:
            rssi_promedio[nombre] = sum(valores) / len(valores)
        else:
            rssi_promedio[nombre] = None

    return rssi_promedio

def rssi_a_distancia(rssi, A):
    return 10 ** ((A - rssi) / (10 * N_PATH_LOSS))

def trilaterar(distancias):
    L = LADO_CUADRADO_M
    d_II = distancias["Baliza Inf-Izquierda"]
    d_ID = distancias["Baliza Inf-Derecha"]
    d_SI = distancias["Baliza Sup-Izquierda"]
    d_SD = distancias["Baliza Sup-Derecha"]

    d_max = 2 * L
    d_II = min(d_II, d_max)
    d_ID = min(d_ID, d_max)
    d_SI = min(d_SI, d_max)
    d_SD = min(d_SD, d_max)

    x_inf = (d_II ** 2 - d_ID ** 2 + L ** 2) / (2 * L)
    x_sup = (d_SI ** 2 - d_SD ** 2 + L ** 2) / (2 * L)
    x = (x_inf + x_sup) / 2

    y_izq = (d_II ** 2 - d_SI ** 2 + L ** 2) / (2 * L)
    y_der = (d_ID ** 2 - d_SD ** 2 + L ** 2) / (2 * L)
    y = (y_izq + y_der) / 2

    margen = 0.5 * L
    if x < -margen or x > L + margen or y < -margen or y > L + margen:
        return None

    x = max(0.0, min(L, x))
    y = max(0.0, min(L, y))
    return x, y

def distancia_al_centro(pos):
    dx = CENTRO[0] - pos[0]
    dy = CENTRO[1] - pos[1]
    return math.sqrt(dx * dx + dy * dy)

def medir_posicion():
    rssi = escanear_balizas()

    if any(v is None for v in rssi.values()):
        faltan = [n for n, v in rssi.items() if v is None]
        print(f"  Faltan balizas: {faltan}")
        return None

    distancias = {n: rssi_a_distancia(rssi[n], A_REF) for n in BALIZAS}
    spread_rssi = max(rssi.values()) - min(rssi.values())
    print(f"  Spread RSSI: {spread_rssi:.1f} dBm")
    print("  RSSI / distancia estimada:")
    for n in BALIZAS:
        print(f"    {n}: {rssi[n]:.1f} dBm → {distancias[n]:.2f} m")

    pos = trilaterar(distancias)
    if pos is None:
        print("  Posición trilaterada inválida (descartada)")
        return None
    print(f"  Posición cruda: ({pos[0]:.2f}, {pos[1]:.2f}) m")
    return pos, spread_rssi

def main():
    set_leds(COLOR_OFF)
    print("=" * 50)
    print("Localización BLE — Objetivo A (centro del cuadrado)")
    print(f"Cuadrado de {LADO_CUADRADO_M} m. Centro en ({CENTRO[0]:.1f}, {CENTRO[1]:.1f}) m")
    print(f"Tolerancia: {TOLERANCIA_CENTRO_M} m | A={A_REF} n={N_PATH_LOSS}")
    print("=" * 50)

    pos_filtrada = None
    err_prev = None
    intentos_centrado = 0
    consecutivos_alejandose = 0
    descartes_seguidos = 0

    while True:
        print("\n--- Escaneando balizas ---")
        set_leds(COLOR_BLUE)
        medida = medir_posicion()

        if medida is None:
            descartes_seguidos += 1
            parar()
            set_leds(COLOR_RED)
            if descartes_seguidos >= 3:
                print("  Muchos descartes → reset del filtro de posición")
                pos_filtrada = None
                err_prev = None
                descartes_seguidos = 0
            time.sleep(1)
            continue
        descartes_seguidos = 0
        pos, spread_rssi = medida

        if pos_filtrada is None:
            pos_filtrada = pos
        else:
            a = POS_FILTER_ALPHA
            pos_filtrada = (a * pos[0] + (1 - a) * pos_filtrada[0],
                            a * pos[1] + (1 - a) * pos_filtrada[1])

        err = distancia_al_centro(pos_filtrada)
        print(f"  Posición filtrada: ({pos_filtrada[0]:.2f}, {pos_filtrada[1]:.2f}) m")
        print(f"  Distancia al centro: {err:.2f} m")

        centrado_geom = err < TOLERANCIA_CENTRO_M
        centrado_simetria = spread_rssi < UMBRAL_SPREAD_RSSI
        if centrado_geom and centrado_simetria:
            intentos_centrado += 1
            parar()
            set_leds(COLOR_GREEN)
            print(f"  ✓ Centrado ({intentos_centrado}/{CONFIRMACIONES_CENTRO} confirmaciones)")
            if intentos_centrado >= CONFIRMACIONES_CENTRO:
                print(f"\n¡Centro alcanzado!  d={err:.2f} m, spread={spread_rssi:.1f} dBm")
                buggy.beepHorn()
                break
            time.sleep(1)
            err_prev = err
            continue

        if intentos_centrado > 0:
            motivos = []
            if not centrado_geom:
                motivos.append(f"err={err:.2f}>{TOLERANCIA_CENTRO_M}")
            if not centrado_simetria:
                motivos.append(f"spread={spread_rssi:.1f}>{UMBRAL_SPREAD_RSSI}")
            print(f"  ✗ Falsa alarma de centrado ({', '.join(motivos)})")
        intentos_centrado = 0

        if err_prev is None:
            accion = "adelante"
        elif err < err_prev - DELTA_MEJORA:
            accion = "adelante"
            consecutivos_alejandose = 0
        elif err > err_prev + DELTA_EMPEORA:
            consecutivos_alejandose += 1
            if consecutivos_alejandose >= MAX_INTENTOS_ALEJANDOSE:
                accion = "girar_180"
                consecutivos_alejandose = 0
            else:
                accion = "girar_90"
        else:
            accion = "adelante"

        prev_str = f"{err_prev:.2f}" if err_prev is not None else "N/A"
        print(f"  Acción: {accion}  (err={err:.2f}, prev={prev_str}, alej={consecutivos_alejandose})")

        if accion == "adelante" and hay_obstaculo_frontal():
            parar()
            set_leds(COLOR_RED)
            print("  Obstáculo a <15 cm — giro 45° y reintento")
            girar_derecha()
            time.sleep_ms(TIEMPO_GIRO_45_MS)
            parar()
            err_prev = err
            continue

        if accion == "adelante":
            set_leds(COLOR_YELLOW)
            adelante()
            time.sleep_ms(TIEMPO_AVANCE_MS)
        elif accion == "girar_90":
            set_leds(COLOR_PURPLE)
            girar_derecha()
            time.sleep_ms(TIEMPO_GIRO_90_MS)
        elif accion == "girar_180":
            set_leds(COLOR_PURPLE)
            girar_derecha()
            time.sleep_ms(TIEMPO_GIRO_180_MS)

        parar()
        time.sleep_ms(200)
        err_prev = err
        err_prev = err

    set_leds(COLOR_GREEN)

main()
