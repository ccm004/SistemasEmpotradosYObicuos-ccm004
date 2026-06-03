# Sistemas Empotrados y Ubicuos

Prácticas de la asignatura **Sistemas Empotrados y Ubicuos** (2º cuatrimestre, Máster).
Cada carpeta `Practica 0N` contiene el código de una práctica. La base de robótica usa el
**Kitronik Pico Robot Buggy** (Raspberry Pi Pico W) y varias placas **ESP32**.

> ⚠️ Las credenciales WiFi del código están sustituidas por marcadores
> (`TU_SSID`, `TU_PASSWORD`). Rellénalas con tus datos antes de desplegar.

## Prácticas

### Practica 01 — Conducción libre (free roaming)
El robot circula evitando obstáculos con los sensores de ultrasonidos delantero y trasero.
Arranque/parada con el botón integrado (mediante interrupción) y LEDs de color según el estado.

### Practica 02 — Sigue-líneas con máquina de estados
Control por pulsaciones del botón (adelante / atrás / avería). El robot sigue una línea con
los sensores IR, esquiva obstáculos, enciende intermitentes y luces de emergencia, y hace
sonar el buzzer mientras retrocede.

### Practica 03 — Actualización OTA + semáforo
*Bootloader de recuperación* en la Pico W: arranca el código de usuario y, si falla, levanta un
servidor web de *recovery* para subir uno nuevo por WiFi. Incluye el control web del robot y el
firmware del **semáforo coordinado** sobre red mallada (ESP32 + painlessMesh).

### Practica 04 — Semáforo + robot cooperativos
Amplía la P3: el robot detecta el punto de acceso WiFi que el semáforo emite en **rojo**, se
detiene y reanuda la marcha al pasar a **verde**; añade un **modo ahorro de energía**. Incluye el
firmware del semáforo en red mesh.

### Practica 05 — Visión con ESP32-CAM
Servidor web de cámara (ESP32-CAM) y un modelo de **Edge Impulse** para detección/clasificación
de imágenes, con el dataset etiquetado y la librería exportada.

### Practica 06 — Localización por BLE
El robot estima su posición por **trilateración** a partir del RSSI de 4 balizas Bluetooth (BLE)
y navega hasta el centro del cuadrado mediante descenso de gradiente con filtrado del ruido.
Incluye el firmware de las balizas (ESP32) y un servidor de logs por UDP.

### Practica 07 — *(pendiente)*

### Practica 08 — *(pendiente)*
