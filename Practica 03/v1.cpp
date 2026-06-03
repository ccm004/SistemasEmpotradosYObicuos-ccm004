#include "painlessMesh.h"
#include <ArduinoJson.h>

// Configuración de la red de malla
#define MESH_PREFIX   "mso328"
#define MESH_PASSWORD "123456789"
#define MESH_PORT     5555

#define SEMAFORO 2  // LED azul integrado

// *** Cambiar a 1 para el grupo opuesto (C-B / H-F) antes de flashear ***
#define GRUPO 0   // 0 → grupo A-D / E-G  |  1 → grupo C-B / H-F

#define T_VERDE  20000  // ms en verde
#define T_AMBAR   5000  // ms en ámbar (parpadeo rápido antes de pasar a rojo)
#define T_ROJO   20000  // ms en rojo

// Intervalos de parpadeo del LED según estado
#define PARPADEO_AMBAR  150   // ms — parpadeo rápido (ámbar)
#define PARPADEO_ROJO   500   // ms — parpadeo lento  (rojo)

Scheduler planificador;
painlessMesh Redmalla;

// Estado actual: Verde (1) | Ámbar (0) | Rojo (-1)
volatile int estado = -1;
unsigned long inicio_estado = 0;
bool led_parpadeo = false;

// Prototipos
void Enviar_mensaje();
void Tarea_semaforo_cb();
void Tarea_vecinos_cb();
void cambiar_estado(int nuevo);

// -------------------------------------------------------------------
// Tareas del planificador
// -------------------------------------------------------------------

// Tarea 1 – Broadcast del estado actual (cada 1-3 s)
Task Tarea_enviar(TASK_SECOND * 1, TASK_FOREVER, &Enviar_mensaje);

// Tarea 2 – Control del LED y transición de estados
Task Tarea_semaforo(PARPADEO_ROJO, TASK_FOREVER, &Tarea_semaforo_cb);

// Tarea 3 – Monitorización de vecinos y coordinación (cada 2 s)
Task Tarea_vecinos(TASK_SECOND * 2, TASK_FOREVER, &Tarea_vecinos_cb);

// -------------------------------------------------------------------
// Cambia el estado del semáforo de forma segura
// -------------------------------------------------------------------
void cambiar_estado(int nuevo) {
    if (estado == nuevo) return;
    estado        = nuevo;
    inicio_estado = millis();
    led_parpadeo  = false;

    // Ajustar el intervalo de la tarea según el nuevo estado
    if (nuevo == 1) {
        Tarea_semaforo.setInterval(PARPADEO_ROJO);   // verde: intervalo no importa (LED fijo)
    } else if (nuevo == 0) {
        Tarea_semaforo.setInterval(PARPADEO_AMBAR);  // ámbar: parpadeo rápido
    } else {
        Tarea_semaforo.setInterval(PARPADEO_ROJO);   // rojo: parpadeo lento
    }

    const char* nombre = (nuevo == 1) ? "VERDE (fijo)" : (nuevo == 0) ? "AMBAR (rapido)" : "ROJO (lento)";
    Serial.printf("[ESTADO] → %s\n", nombre);
}

// -------------------------------------------------------------------
// Tarea 1: Envía el estado por broadcast
// -------------------------------------------------------------------
void Enviar_mensaje() {
    StaticJsonDocument<256> doc;
    doc["id"]     = Redmalla.getNodeId();
    doc["grupo"]  = GRUPO;
    doc["estado"] = estado;

    // Tiempo restante en el estado actual
    unsigned long duracion = (estado == 1) ? T_VERDE : (estado == 0) ? T_AMBAR : T_ROJO;
    doc["tiempo"] = (long)(duracion - (millis() - inicio_estado)) / 1000;

    char mensaje[256];
    serializeJson(doc, mensaje);
    Redmalla.sendBroadcast(mensaje);

    const char* nombre_estado = (estado == 1) ? "VERDE" : (estado == 0) ? "AMBAR" : "ROJO";
    Serial.printf("[TX] estado=%s restante=%ld s\n", nombre_estado, doc["tiempo"].as<long>());

    Tarea_enviar.setInterval(random(TASK_SECOND * 1, TASK_SECOND * 3));
}

// -------------------------------------------------------------------
// Tarea 2: Controla el LED y gestiona las transiciones de estado
// -------------------------------------------------------------------
void Tarea_semaforo_cb() {
    unsigned long ahora = millis();
    unsigned long transcurrido = ahora - inicio_estado;

    if (estado == 1) {
        // Verde: LED fijo encendido
        digitalWrite(SEMAFORO, HIGH);

        // Cuando queda T_AMBAR para acabar, pasar a ámbar
        if (transcurrido >= T_VERDE - T_AMBAR) {
            Serial.printf("[SEMAFORO] Verde → Ambar\n");
            cambiar_estado(0);
        }

    } else if (estado == 0) {
        // Ámbar: parpadeo rápido (intervalo PARPADEO_AMBAR)
        led_parpadeo = !led_parpadeo;
        digitalWrite(SEMAFORO, led_parpadeo ? HIGH : LOW);

        if (transcurrido >= T_AMBAR) {
            Serial.printf("[SEMAFORO] Ambar → Rojo\n");
            cambiar_estado(-1);
        }

    } else {
        // Rojo: parpadeo lento (intervalo PARPADEO_ROJO)
        led_parpadeo = !led_parpadeo;
        digitalWrite(SEMAFORO, led_parpadeo ? HIGH : LOW);

        if (transcurrido >= T_ROJO) {
            Serial.printf("[SEMAFORO] Rojo → Verde\n");
            cambiar_estado(1);
        }
    }
}

// -------------------------------------------------------------------
// Tarea 3: Comprueba vecinos activos y su estado en la malla
// -------------------------------------------------------------------
void Tarea_vecinos_cb() {
    std::list<uint32_t> vecinos = Redmalla.getNodeList();
    const char* nombre_estado = (estado == 1) ? "VERDE" : (estado == 0) ? "AMBAR" : "ROJO";
    Serial.printf("[VECINOS] Nodos conectados: %d | Mi estado: %s | Topología: %s\n",
                  (int)vecinos.size(), nombre_estado,
                  Redmalla.subConnectionJson().c_str());
}

// -------------------------------------------------------------------
// Recibe mensajes y coordina el estado con el otro semáforo
//
// Regla: mismo grupo → mismo estado | grupo opuesto → estado contrario
// El ámbar (0) se trata como transición: el opuesto también pasa a ámbar
// -------------------------------------------------------------------
void Mensaje_recibido(uint32_t remitente, String &mensaje) {
    Serial.printf("[RX] desde %u: %s\n", remitente, mensaje.c_str());

    StaticJsonDocument<256> doc;
    if (deserializeJson(doc, mensaje)) return;
    if (!doc.containsKey("grupo")) return;

    int estado_remoto = doc["estado"] | 0;
    bool mismo_grupo  = (doc["grupo"].as<int>() == GRUPO);

    // Mismo grupo → copiar estado | Grupo opuesto → estado contrario
    // Si el remitente está en ÁMBAR, el grupo opuesto NO actúa todavía:
    // debe esperar a que el remitente llegue a ROJO para pasar a VERDE.
    int estado_esperado;
    if (estado_remoto == 0) {
        if (mismo_grupo) {
            estado_esperado = 0;   // mismo grupo: también entra en ámbar
        } else {
            return;                // grupo opuesto: espera a que llegue a ROJO
        }
    } else {
        estado_esperado = mismo_grupo ? estado_remoto : -estado_remoto;
    }

    if (estado != estado_esperado) {
        const char* nombre = (estado_esperado == 1) ? "VERDE" : (estado_esperado == 0) ? "AMBAR" : "ROJO";
        Serial.printf("[COORD] Nodo %u (%s) → forzando %s\n",
                      remitente,
                      mismo_grupo ? "mismo grupo" : "grupo opuesto",
                      nombre);
        cambiar_estado(estado_esperado);
    }
}

void Nueva_conexion(uint32_t Id_nodo) {
    Serial.printf("[MESH] Nueva conexión: nodo=%u\n", Id_nodo);
}

void Cambio_conexion() {
    Serial.printf("[MESH] Cambio en conexiones\n");
}

void Sincronizar_reloj(int32_t offset) {
    Serial.printf("[MESH] Reloj sincronizado | tiempo=%u offset=%d\n",
                  Redmalla.getNodeTime(), offset);
}

// -------------------------------------------------------------------
// SETUP
// -------------------------------------------------------------------
void setup() {
    Serial.begin(115200);
    pinMode(SEMAFORO, OUTPUT);
    digitalWrite(SEMAFORO, LOW);

    Redmalla.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);

    Redmalla.init(MESH_PREFIX, MESH_PASSWORD, &planificador, MESH_PORT);
    Redmalla.onReceive(&Mensaje_recibido);
    Redmalla.onNewConnection(&Nueva_conexion);
    Redmalla.onChangedConnections(&Cambio_conexion);
    Redmalla.onNodeTimeAdjusted(&Sincronizar_reloj);

    // Registrar y arrancar las tres tareas
    planificador.addTask(Tarea_enviar);
    planificador.addTask(Tarea_semaforo);
    planificador.addTask(Tarea_vecinos);
    Tarea_enviar.enable();
    Tarea_semaforo.enable();
    Tarea_vecinos.enable();

    // Estado inicial según grupo definido en tiempo de compilación
    int inicial = (GRUPO == 0) ? 1 : -1;  // grupo 0 → VERDE | grupo 1 → ROJO
    cambiar_estado(inicial);
    Serial.printf("[SETUP] nodo=%u grupo=%d → %s\n",
                  Redmalla.getNodeId(), GRUPO, inicial == 1 ? "VERDE" : "ROJO");
}

// -------------------------------------------------------------------
// LOOP – solo mantiene la malla activa, sin lógica ni delay()
// -------------------------------------------------------------------
void loop() {
    Redmalla.update();
}
