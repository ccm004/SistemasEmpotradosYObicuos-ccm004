#include "painlessMesh.h"
#include <ArduinoJson.h>

// Parámetros de la red mallada
#define PREFIJO_MALLA  "mso328"
#define CLAVE_MALLA    "123456789"
#define PUERTO_MALLA   5555

#define PIN_LED 2  // LED azul integrado

// *** Poner a 1 para el grupo opuesto (C-B / H-F) antes de programar ***
#define ID_GRUPO 0   // 0 → grupo A-D / E-G  |  1 → grupo C-B / H-F

#define DUR_VERDE  20000  // ms en verde
#define DUR_AMBAR   5000  // ms en ámbar (parpadeo rápido antes del rojo)
#define DUR_ROJO   20000  // ms en rojo

// Intervalos de parpadeo del LED según el estado
#define INTERVALO_AMBAR  150   // ms — parpadeo rápido (ámbar)
#define INTERVALO_ROJO   500   // ms — parpadeo lento  (rojo)

Scheduler agenda;
painlessMesh malla;

// Estado actual: Verde (1) | Ámbar (0) | Rojo (-1)
volatile int faseActual = -1;
unsigned long instanteFase = 0;
bool ledEncendido = false;

// Prototipos
void difundirEstado();
void controlarSemaforo();
void reportarVecinos();
void fijarFase(int nuevaFase);

// -------------------------------------------------------------------
// Tareas del planificador
// -------------------------------------------------------------------

// Tarea 1 – Broadcast del estado actual (cada 1-3 s)
Task tareaDifusion(TASK_SECOND * 1, TASK_FOREVER, &difundirEstado);

// Tarea 2 – Control del LED y transición de estados
Task tareaSemaforo(INTERVALO_ROJO, TASK_FOREVER, &controlarSemaforo);

// Tarea 3 – Monitorización de vecinos y coordinación (cada 2 s)
Task tareaVecinos(TASK_SECOND * 2, TASK_FOREVER, &reportarVecinos);

// -------------------------------------------------------------------
// Cambia el estado del semáforo de forma controlada
// -------------------------------------------------------------------
void fijarFase(int nuevaFase) {
    if (faseActual == nuevaFase) return;
    faseActual   = nuevaFase;
    instanteFase = millis();
    ledEncendido = false;

    // Ajustar el intervalo de la tarea según el nuevo estado
    if (nuevaFase == 1) {
        tareaSemaforo.setInterval(INTERVALO_ROJO);   // verde: el intervalo no importa (LED fijo)
    } else if (nuevaFase == 0) {
        tareaSemaforo.setInterval(INTERVALO_AMBAR);  // ámbar: parpadeo rápido
    } else {
        tareaSemaforo.setInterval(INTERVALO_ROJO);   // rojo: parpadeo lento
    }

    const char* etiqueta = (nuevaFase == 1) ? "VERDE (fijo)" : (nuevaFase == 0) ? "AMBAR (rapido)" : "ROJO (lento)";
    Serial.printf("[ESTADO] → %s\n", etiqueta);
}

// -------------------------------------------------------------------
// Tarea 1: Difunde el estado por broadcast
// -------------------------------------------------------------------
void difundirEstado() {
    StaticJsonDocument<256> json;
    json["id"]     = malla.getNodeId();
    json["grupo"]  = ID_GRUPO;
    json["estado"] = faseActual;

    // Tiempo restante en el estado actual
    unsigned long tiempoTotalFase = (faseActual == 1) ? DUR_VERDE : (faseActual == 0) ? DUR_AMBAR : DUR_ROJO;
    json["tiempo"] = (long)(tiempoTotalFase - (millis() - instanteFase)) / 1000;

    char buffer[256];
    serializeJson(json, buffer);
    malla.sendBroadcast(buffer);

    const char* textoEstado = (faseActual == 1) ? "VERDE" : (faseActual == 0) ? "AMBAR" : "ROJO";
    Serial.printf("[TX] estado=%s restante=%ld s\n", textoEstado, json["tiempo"].as<long>());

    tareaDifusion.setInterval(random(TASK_SECOND * 1, TASK_SECOND * 3));
}

// -------------------------------------------------------------------
// Tarea 2: Gestiona el LED y las transiciones de estado
// -------------------------------------------------------------------
void controlarSemaforo() {
    unsigned long instanteAhora = millis();
    unsigned long tiempoEnFase = instanteAhora - instanteFase;

    if (faseActual == 1) {
        // Verde: LED fijo encendido
        digitalWrite(PIN_LED, HIGH);

        // Cuando queda DUR_AMBAR para terminar, pasar a ámbar
        if (tiempoEnFase >= DUR_VERDE - DUR_AMBAR) {
            Serial.printf("[SEMAFORO] Verde → Ambar\n");
            fijarFase(0);
        }

    } else if (faseActual == 0) {
        // Ámbar: parpadeo rápido (intervalo INTERVALO_AMBAR)
        ledEncendido = !ledEncendido;
        digitalWrite(PIN_LED, ledEncendido ? HIGH : LOW);

        if (tiempoEnFase >= DUR_AMBAR) {
            Serial.printf("[SEMAFORO] Ambar → Rojo\n");
            fijarFase(-1);
        }

    } else {
        // Rojo: parpadeo lento (intervalo INTERVALO_ROJO)
        ledEncendido = !ledEncendido;
        digitalWrite(PIN_LED, ledEncendido ? HIGH : LOW);

        if (tiempoEnFase >= DUR_ROJO) {
            Serial.printf("[SEMAFORO] Rojo → Verde\n");
            fijarFase(1);
        }
    }
}

// -------------------------------------------------------------------
// Tarea 3: Revisa los vecinos activos y su estado en la malla
// -------------------------------------------------------------------
void reportarVecinos() {
    std::list<uint32_t> listaNodos = malla.getNodeList();
    const char* textoEstado = (faseActual == 1) ? "VERDE" : (faseActual == 0) ? "AMBAR" : "ROJO";
    Serial.printf("[VECINOS] Nodos conectados: %d | Mi estado: %s | Topología: %s\n",
                  (int)listaNodos.size(), textoEstado,
                  malla.subConnectionJson().c_str());
}

// -------------------------------------------------------------------
// Recibe mensajes y coordina el estado con el otro semáforo
//
// Regla: mismo grupo → mismo estado | grupo opuesto → estado contrario
// El ámbar (0) es una transición: el opuesto también pasa a ámbar
// -------------------------------------------------------------------
void alRecibirMensaje(uint32_t emisor, String &textoJson) {
    Serial.printf("[RX] desde %u: %s\n", emisor, textoJson.c_str());

    StaticJsonDocument<256> json;
    if (deserializeJson(json, textoJson)) return;
    if (!json.containsKey("grupo")) return;

    int faseRemota   = json["estado"] | 0;
    bool mismoGrupo  = (json["grupo"].as<int>() == ID_GRUPO);

    // Mismo grupo → copiar estado | Grupo opuesto → estado contrario
    // Si el emisor está en ÁMBAR, el grupo opuesto NO actúa todavía:
    // debe esperar a que el emisor llegue a ROJO para pasar a VERDE.
    int faseObjetivo;
    if (faseRemota == 0) {
        if (mismoGrupo) {
            faseObjetivo = 0;   // mismo grupo: también entra en ámbar
        } else {
            return;             // grupo opuesto: espera a que llegue a ROJO
        }
    } else {
        faseObjetivo = mismoGrupo ? faseRemota : -faseRemota;
    }

    if (faseActual != faseObjetivo) {
        const char* etiqueta = (faseObjetivo == 1) ? "VERDE" : (faseObjetivo == 0) ? "AMBAR" : "ROJO";
        Serial.printf("[COORD] Nodo %u (%s) → forzando %s\n",
                      emisor,
                      mismoGrupo ? "mismo grupo" : "grupo opuesto",
                      etiqueta);
        fijarFase(faseObjetivo);
    }
}

void alNuevaConexion(uint32_t idNodo) {
    Serial.printf("[MESH] Nueva conexión: nodo=%u\n", idNodo);
}

void alCambioConexion() {
    Serial.printf("[MESH] Cambio en conexiones\n");
}

void alSincronizarReloj(int32_t desfase) {
    Serial.printf("[MESH] Reloj sincronizado | tiempo=%u offset=%d\n",
                  malla.getNodeTime(), desfase);
}

// -------------------------------------------------------------------
// SETUP
// -------------------------------------------------------------------
void setup() {
    Serial.begin(115200);
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    malla.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);

    malla.init(PREFIJO_MALLA, CLAVE_MALLA, &agenda, PUERTO_MALLA);
    malla.onReceive(&alRecibirMensaje);
    malla.onNewConnection(&alNuevaConexion);
    malla.onChangedConnections(&alCambioConexion);
    malla.onNodeTimeAdjusted(&alSincronizarReloj);

    // Registrar y arrancar las tres tareas
    agenda.addTask(tareaDifusion);
    agenda.addTask(tareaSemaforo);
    agenda.addTask(tareaVecinos);
    tareaDifusion.enable();
    tareaSemaforo.enable();
    tareaVecinos.enable();

    // Estado inicial según el grupo fijado en tiempo de compilación
    int faseInicial = (ID_GRUPO == 0) ? 1 : -1;  // grupo 0 → VERDE | grupo 1 → ROJO
    fijarFase(faseInicial);
    Serial.printf("[SETUP] nodo=%u grupo=%d → %s\n",
                  malla.getNodeId(), ID_GRUPO, faseInicial == 1 ? "VERDE" : "ROJO");
}

// -------------------------------------------------------------------
// LOOP – solo mantiene la malla activa, sin lógica ni delay()
// -------------------------------------------------------------------
void loop() {
    malla.update();
}
