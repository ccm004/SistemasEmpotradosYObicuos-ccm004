#include "painlessMesh.h"
#include <ArduinoJson.h>
#include <WiFi.h>   // [EJ1] / [EJ2]  AP WiFi propio y recuento de robots conectados

// -------------------------------------------------------------------
// Parámetros de la red mallada (Práctica 3 — sin cambios)
// -------------------------------------------------------------------
#define PREFIJO_MALLA  "mso328"
#define CLAVE_MALLA    "123456789"
#define PUERTO_MALLA   5555

#define PIN_LED_ROJO   18
#define PIN_LED_AMBAR  19
#define PIN_LED_VERDE  21

// *** Ajustar antes de programar la placa ***
#define ID_GRUPO   0   // 0 → grupo A-D / E-G  |  1 → grupo C-B / H-F
#define ES_MASTER  1   // 1 → MASTER (manda en el grupo) | 0 → SLAVE (sigue al master)

// -------------------------------------------------------------------
// Duraciones de la máquina de estados
//   [EJ5] El verde se multiplica por cinco (de 1 a 5 min) para que el
//         tráfico fluya mejor.
//   [EJ5] El rojo permanece en 20 s: tiempo mínimo asegurado para que
//         un peatón cruce caminando despacio.
// -------------------------------------------------------------------
#define DUR_VERDE  30000  // [EJ5] 5 min en verde
#define DUR_AMBAR   5000  // ms en ámbar / rojo_espera
#define DUR_ROJO   20000  // ms en rojo (mínimo asegurado para el peatón)

#define INTERVALO_PARPADEO  150   // ms — parpadeo rápido del ámbar

// -------------------------------------------------------------------
// [EJ1] / [EJ2]  Punto de acceso WiFi del semáforo
//   - Solo se levanta cuando el semáforo está en ROJO (o ROJO_ESPERA).
//   - Permite que el robot mida el RSSI y se enganche al semáforo más
//     próximo. Cuando pasa a VERDE el AP se apaga y el robot continúa.
//   - [EJ2] El semáforo cuenta los robots conectados a su AP; si hay
//     ≥ UMBRAL_ROBOTS, el MASTER puede adelantar el verde sin esperar
//     a que termine DUR_ROJO.
// -------------------------------------------------------------------
#define CLAVE_AP            "robot1234"
#define UMBRAL_ROBOTS       3            // [EJ2] mínimo de robots para adelantar el verde
#define ESPERA_MIN_ANTICIPAR 5000        // [EJ2] tiempo mínimo en rojo antes de adelantar

// -------------------------------------------------------------------
// [EJ4] / [EJ5]  Sensor táctil de petición de peatón
//   - La ISR es mínima: únicamente levanta un flag.
//   - [EJ5] El MASTER, estando en VERDE, fuerza el paso a ROJO siempre
//     que haya transcurrido al menos 1 min desde la última parada. Solo
//     se atiende la primera petición de cada ciclo.
// -------------------------------------------------------------------
#define PIN_TACTIL_PEATON  T0           // [EJ4] sensor táctil T0 (GPIO 4)
#define UMBRAL_TACTIL      40           // [EJ4] umbral del touchpad
#define ESPERA_ENTRE_PARADAS 60000      // [EJ5] 1 min entre paradas

// Estados: VERDE=1 | AMBAR=0 | ROJO=-1 | ROJO_ESPERA=-2

Scheduler agenda;
painlessMesh malla;

volatile int faseActual = -1;
unsigned long instanteFase = 0;
bool ledEncendido = false;

// [EJ1] flag del AP propio (levantado/apagado)
bool apEncendido = false;

// [EJ4] / [EJ5] estado de la petición de peatón
volatile bool solicitudPeaton  = false;  // [EJ4] la ISR lo pone a true
unsigned long instanteUltimaParada = 0;   // [EJ5] cooldown de 1 min
bool solicitudAtendida         = false;   // [EJ5] solo la primera por ciclo

// Prototipos
void difundirEstado();
void controlarSemaforo();
void reportarVecinos();
void fijarFase(int nuevaFase);
void encenderAp();      // [EJ1]
void apagarAp();        // [EJ1]
void IRAM_ATTR isrPeaton();  // [EJ4]

// -------------------------------------------------------------------
// Tareas del planificador
// -------------------------------------------------------------------
Task tareaDifusion(TASK_SECOND * 1, TASK_FOREVER, &difundirEstado);
Task tareaSemaforo(INTERVALO_PARPADEO, TASK_FOREVER, &controlarSemaforo);
Task tareaVecinos(TASK_SECOND * 2, TASK_FOREVER, &reportarVecinos);

// -------------------------------------------------------------------
// Texto legible de cada estado
// -------------------------------------------------------------------
const char* etiquetaFase(int fase) {
    switch (fase) {
        case  1: return "VERDE";
        case  0: return "AMBAR";
        case -1: return "ROJO";
        case -2: return "ROJO_ESPERA";
        default: return "?";
    }
}

// -------------------------------------------------------------------
// [EJ4]  ISR del touchpad — tiene que ser MÍNIMA: solo levanta un flag.
//        Nada de Serial.print ni lógica pesada aquí dentro.
// -------------------------------------------------------------------
void IRAM_ATTR isrPeaton() {
    solicitudPeaton = true;
}

// -------------------------------------------------------------------
// [EJ1]  Encender / apagar el AP WiFi propio del semáforo
// -------------------------------------------------------------------
void encenderAp() {
    if (apEncendido) return;
    char nombreRedAp[32];
    snprintf(nombreRedAp, sizeof(nombreRedAp), "SEMAFORO_ROJO_%u", malla.getNodeId());
    WiFi.softAP(nombreRedAp, CLAVE_AP);
    apEncendido = true;
    Serial.printf("[EJ1][AP ON ] %s — robots pueden conectarse\n", nombreRedAp);
}

void apagarAp() {
    if (!apEncendido) return;
    WiFi.softAPdisconnect(true);
    apEncendido = false;
    Serial.println("[EJ1][AP OFF] — el robot puede continuar (verde)");
}

// -------------------------------------------------------------------
// Cambia el estado del semáforo de forma controlada
// -------------------------------------------------------------------
void fijarFase(int nuevaFase) {
    if (faseActual == nuevaFase) return;
    faseActual   = nuevaFase;
    instanteFase = millis();
    ledEncendido = false;

    digitalWrite(PIN_LED_ROJO,  LOW);
    digitalWrite(PIN_LED_AMBAR, LOW);
    digitalWrite(PIN_LED_VERDE, LOW);

    // El ámbar necesita intervalo corto para parpadear; el resto usa 1 s (LED fijo)
    tareaSemaforo.setInterval(nuevaFase == 0 ? INTERVALO_PARPADEO : TASK_SECOND);

    // [EJ1] AP visible solo en rojo (incluido ROJO_ESPERA)
    if (nuevaFase == -1 || nuevaFase == -2) encenderAp();
    else                                    apagarAp();

    // [EJ5] Al entrar en ROJO arrancamos el cooldown y rearmamos la petición
    if (nuevaFase == -1) {
        instanteUltimaParada = millis();
        solicitudAtendida    = false;
    }

    Serial.printf("[ESTADO][%s] → %s\n", ES_MASTER ? "MASTER" : "SLAVE", etiquetaFase(nuevaFase));
}

// -------------------------------------------------------------------
// Tarea 1: Difunde el estado por broadcast
//   [EJ2] El mensaje lleva ahora el número de robots conectados a
//         nuestro AP, para que el MASTER pueda decidir si adelanta el
//         cambio a verde.
// -------------------------------------------------------------------
void difundirEstado() {
    StaticJsonDocument<256> json;
    json["id"]     = malla.getNodeId();
    json["grupo"]  = ID_GRUPO;
    json["master"] = ES_MASTER;
    json["estado"] = faseActual;

    // [EJ2] robots conectados a nuestro AP (0 si el AP está apagado)
    unsigned int numRobots = apEncendido ? WiFi.softAPgetStationNum() : 0;
    json["robots"] = numRobots;

    unsigned long tiempoTotalFase = (faseActual == 1) ? DUR_VERDE : (faseActual == -1) ? DUR_ROJO : DUR_AMBAR;
    json["tiempo"] = (long)(tiempoTotalFase - (millis() - instanteFase)) / 1000;

    char buffer[256];
    serializeJson(json, buffer);
    malla.sendBroadcast(buffer);

    Serial.printf("[TX][%s] estado=%s robots=%u restante=%ld s\n",
                  ES_MASTER ? "MASTER" : "SLAVE",
                  etiquetaFase(faseActual), numRobots, json["tiempo"].as<long>());

    tareaDifusion.setInterval(random(TASK_SECOND * 1, TASK_SECOND * 3));
}

// -------------------------------------------------------------------
// Tarea 2: Gestiona el LED y las transiciones de estado
//   - Todos los nodos refrescan el LED (master y slave).
//   - Solo el MASTER avanza la máquina de estados, atiende a los
//     peatones [EJ5] y adelanta el verde si hay muchos robots [EJ2].
// -------------------------------------------------------------------
void controlarSemaforo() {
    unsigned long tiempoEnFase = millis() - instanteFase;

    // Refrescar el LED según el estado actual (master y slave)
    if (faseActual == 1) {
        digitalWrite(PIN_LED_VERDE, HIGH);
    } else if (faseActual == 0) {
        ledEncendido = !ledEncendido;
        digitalWrite(PIN_LED_AMBAR, ledEncendido ? HIGH : LOW);
    } else {
        // ROJO (-1) y ROJO_ESPERA (-2): LED rojo fijo
        digitalWrite(PIN_LED_ROJO, HIGH);
    }

    // Solo el MASTER avanza la máquina de estados
    if (!ES_MASTER) return;

    // ---------------------------------------------------------------
    // [EJ5]  Petición de peatón estando en VERDE
    //        - el verde dura 5 min, pero si un peatón toca el sensor
    //          forzamos VERDE → ÁMBAR → ROJO (máquina normal).
    //        - debe haber pasado al menos ESPERA_ENTRE_PARADAS (1 min)
    //          desde la última parada.
    //        - solo se atiende la primera petición del ciclo.
    // ---------------------------------------------------------------
    if (faseActual == 1 && solicitudPeaton && !solicitudAtendida) {
        solicitudPeaton = false;
        if (millis() - instanteUltimaParada >= ESPERA_ENTRE_PARADAS) {
            Serial.println("[EJ5][PEATON] solicitud aceptada → verde → ámbar");
            solicitudAtendida = true;
            fijarFase(0);  // entra en la máquina normal: ámbar y luego rojo
            return;
        } else {
            unsigned long segsRestantes = (ESPERA_ENTRE_PARADAS - (millis() - instanteUltimaParada)) / 1000;
            Serial.printf("[EJ5][PEATON] solicitud descartada (cooldown: %lus restantes)\n", segsRestantes);
        }
    }

    // ---------------------------------------------------------------
    // [EJ2]  Adelantar el verde si hay ≥ UMBRAL_ROBOTS conectados
    //        - solo si llevamos ESPERA_MIN_ANTICIPAR ms en rojo, para
    //          evitar oscilaciones nada más entrar en rojo.
    //        - pasamos a ROJO_ESPERA: eso lleva al grupo opuesto a
    //          ÁMBAR y, tras DUR_AMBAR, este grupo pasa a VERDE.
    // ---------------------------------------------------------------
    if (faseActual == -1 && tiempoEnFase >= ESPERA_MIN_ANTICIPAR) {
        unsigned int numRobots = apEncendido ? WiFi.softAPgetStationNum() : 0;
        if (numRobots >= UMBRAL_ROBOTS) {
            Serial.printf("[EJ2][MASTER] %u robots esperando → anticipando verde\n", numRobots);
            fijarFase(-2);
            return;
        }
    }

    // ---------------------------------------------------------------
    // Máquina de estados normal (Práctica 3)
    // ---------------------------------------------------------------
    if (faseActual == 1 && tiempoEnFase >= DUR_VERDE - DUR_AMBAR) {
        Serial.println("[MASTER] Verde → Ambar");
        fijarFase(0);
    } else if (faseActual == 0 && tiempoEnFase >= DUR_AMBAR) {
        Serial.println("[MASTER] Ambar → Rojo");
        fijarFase(-1);
    } else if (faseActual == -1 && tiempoEnFase >= DUR_ROJO) {
        Serial.println("[MASTER] Rojo → Rojo_Espera (dando tiempo al grupo contrario)");
        fijarFase(-2);
    } else if (faseActual == -2 && tiempoEnFase >= DUR_AMBAR) {
        Serial.println("[MASTER] Rojo_Espera → Verde");
        fijarFase(1);
    }
}

// -------------------------------------------------------------------
// Tarea 3: Monitorización de vecinos
//   [EJ2] Incluimos también el nº de robots conectados a nuestro AP.
// -------------------------------------------------------------------
void reportarVecinos() {
    std::list<uint32_t> listaNodos = malla.getNodeList();
    unsigned int numRobots = apEncendido ? WiFi.softAPgetStationNum() : 0;
    Serial.printf("[VECINOS][%s] Nodos: %d | Robots: %u | Estado: %s | Topología: %s\n",
                  ES_MASTER ? "MASTER" : "SLAVE",
                  (int)listaNodos.size(), numRobots, etiquetaFase(faseActual),
                  malla.subConnectionJson().c_str());
}

// -------------------------------------------------------------------
// Recepción de mensajes y coordinación del estado
//
// SLAVE  → obedece al MASTER de su mismo grupo (copia el estado exacto)
// MASTER → coordina con el MASTER del grupo opuesto:
//            VERDE       → ROJO
//            AMBAR       → ROJO
//            ROJO        → VERDE
//            ROJO_ESPERA → AMBAR
//
// [EJ2] El MASTER también escucha a los SLAVES de su mismo grupo para
//       saber cuántos robots tienen conectados. Si alguno reporta
//       ≥ UMBRAL_ROBOTS, adelanta el cambio a verde.
// -------------------------------------------------------------------
void alRecibirMensaje(uint32_t emisor, String &textoJson) {
    Serial.printf("[RX] desde %u: %s\n", emisor, textoJson.c_str());

    StaticJsonDocument<256> json;
    if (deserializeJson(json, textoJson)) return;
    if (!json.containsKey("grupo"))  return;
    if (!json.containsKey("estado")) return;

    int  faseRemota          = json["estado"] | 0;
    bool mismoGrupo          = (json["grupo"].as<int>() == ID_GRUPO);
    bool emisorMaster        = (json["master"] | 0) == 1;
    unsigned int numRobotsRx = json["robots"] | 0;   // [EJ2]

    if (!ES_MASTER) {
        // SLAVE: solo obedece a mensajes de un MASTER
        if (!emisorMaster) return;

        int faseObjetivo;
        if (mismoGrupo) {
            faseObjetivo = faseRemota;
        } else {
            switch (faseRemota) {
                case  1:  faseObjetivo = -1; break;
                case  0:  faseObjetivo = -1; break;
                case -1:  faseObjetivo =  1; break;
                case -2:  faseObjetivo =  0; break;
                default:  return;
            }
        }

        if (faseActual != faseObjetivo) {
            Serial.printf("[SLAVE] Master %u (%s) en %s → forzando %s\n",
                          emisor, mismoGrupo ? "mismo grupo" : "grupo opuesto",
                          etiquetaFase(faseRemota), etiquetaFase(faseObjetivo));
            fijarFase(faseObjetivo);
        }
        return;
    }

    // ---- MASTER ----

    // [EJ2] Un slave de mi grupo me dice cuántos robots tiene.
    //       Si estoy en rojo y reporta ≥ UMBRAL_ROBOTS, adelanto el verde.
    if (mismoGrupo && !emisorMaster
        && faseActual == -1
        && numRobotsRx >= UMBRAL_ROBOTS
        && (millis() - instanteFase) >= ESPERA_MIN_ANTICIPAR) {
        Serial.printf("[EJ2][MASTER] slave %u reporta %u robots → anticipando verde\n",
                      emisor, numRobotsRx);
        fijarFase(-2);
        return;
    }

    // El resto de la coordinación es entre masters de grupos opuestos
    if (!emisorMaster) return;
    if (mismoGrupo)    return;

    int faseObjetivo;
    switch (faseRemota) {
        case  1:  faseObjetivo = -1; break;
        case  0:  faseObjetivo =  0; break;
        case -1:  faseObjetivo =  1; break;
        case -2:  faseObjetivo =  0; break;
        default:  return;
    }

    if (faseActual != faseObjetivo) {
        Serial.printf("[MASTER] Grupo opuesto %u en %s → forzando %s\n",
                      emisor, etiquetaFase(faseRemota), etiquetaFase(faseObjetivo));
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
    pinMode(PIN_LED_ROJO,  OUTPUT); digitalWrite(PIN_LED_ROJO,  LOW);
    pinMode(PIN_LED_AMBAR, OUTPUT); digitalWrite(PIN_LED_AMBAR, LOW);
    pinMode(PIN_LED_VERDE, OUTPUT); digitalWrite(PIN_LED_VERDE, LOW);

    // [EJ4] Activar la interrupción táctil del peatón (sensor T0)
    touchAttachInterrupt(PIN_TACTIL_PEATON, isrPeaton, UMBRAL_TACTIL);
    Serial.printf("[EJ4] Interrupción táctil activada en T0 (umbral=%d)\n", UMBRAL_TACTIL);

    malla.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
    malla.init(PREFIJO_MALLA, CLAVE_MALLA, &agenda, PUERTO_MALLA);
    malla.onReceive(&alRecibirMensaje);
    malla.onNewConnection(&alNuevaConexion);
    malla.onChangedConnections(&alCambioConexion);
    malla.onNodeTimeAdjusted(&alSincronizarReloj);

    agenda.addTask(tareaDifusion);
    agenda.addTask(tareaSemaforo);
    agenda.addTask(tareaVecinos);
    tareaDifusion.enable();
    tareaSemaforo.enable();
    tareaVecinos.enable();

    // [EJ5] Permitir que la primera petición se atienda sin esperar el cooldown
    instanteUltimaParada = millis() - ESPERA_ENTRE_PARADAS;

    // Estado inicial según el grupo (el slave lo recibirá por la malla)
    int faseInicial = (ID_GRUPO == 0) ? 1 : -1;
    fijarFase(faseInicial);

    Serial.printf("[SETUP] nodo=%u grupo=%d rol=%s → %s\n",
                  malla.getNodeId(), ID_GRUPO,
                  ES_MASTER ? "MASTER" : "SLAVE",
                  etiquetaFase(faseInicial));
}

// -------------------------------------------------------------------
// LOOP
// -------------------------------------------------------------------
void loop() {
    malla.update();
}
