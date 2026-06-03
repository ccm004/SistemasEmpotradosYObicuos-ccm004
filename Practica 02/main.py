from PicoAutonomousRobotics import KitronikPicoRobotBuggy
from time import sleep_ms, ticks_ms, ticks_diff

robot = KitronikPicoRobotBuggy()

colorApagado = (0, 0, 0)
colorAmbar = (255, 150, 0)

estado = "PARADO"
cronoParpadeo = ticks_ms()
parpadeoActivo = False

ventanaActiva = False
ventanaInicio = 0
numPulsaciones = 0
ultimoValorBoton = False


def ponerColorLeds(color):
    for indiceLed in range(4):
        robot.setLED(indiceLed, color)


def actualizarParpadeo():
    global cronoParpadeo, parpadeoActivo
    if ticks_diff(ticks_ms(), cronoParpadeo) > 300:
        parpadeoActivo = not parpadeoActivo
        cronoParpadeo = ticks_ms()


ponerColorLeds(colorApagado)
robot.show()

while True:
    actualizarParpadeo()

    valorBotonActual = robot.button.value()

    if valorBotonActual and not ultimoValorBoton:
        if not ventanaActiva:
            ventanaActiva = True
            ventanaInicio = ticks_ms()
            numPulsaciones = 1
            estado = "PARADO"
        else:
            numPulsaciones += 1
            if numPulsaciones == 2:
                estado = "ATRAS"
            elif numPulsaciones >= 3:
                estado = "ADELANTE"
                ventanaActiva = False
                numPulsaciones = 0

    ultimoValorBoton = valorBotonActual

    if ventanaActiva and ticks_diff(ticks_ms(), ventanaInicio) >= 5000:
        ventanaActiva = False
        numPulsaciones = 0

    if estado == "ATRAS" and parpadeoActivo:
        robot.soundFrequency(1000)
    else:
        robot.silence()

    if estado == "PARADO":
        robot.motorOn("l", "f", 0)
        robot.motorOn("r", "f", 0)

        if parpadeoActivo:
            ponerColorLeds(colorAmbar)
        else:
            ponerColorLeds(colorApagado)

    elif estado == "ADELANTE":
        distancia = robot.getDistance("f")

        if 0 < distancia <= 15:
            robot.motorOn("l", "f", 20)
            robot.motorOn("r", "r", 20)

            if parpadeoActivo:
                robot.setLED(1, colorAmbar); robot.setLED(2, colorAmbar)
            else:
                robot.setLED(1, colorApagado); robot.setLED(2, colorApagado)
            robot.setLED(0, colorApagado); robot.setLED(3, colorApagado)

        else:
            valorCentro = robot.getRawLFValue("c")
            valorIzquierda = robot.getRawLFValue("l")
            valorDerecha = robot.getRawLFValue("r")

            if valorCentro < 30000:
                if valorIzquierda < valorDerecha:
                    robot.motorOn("l", "f", 20)
                    robot.motorOn("r", "r", 20)
                    if parpadeoActivo:
                        robot.setLED(1, colorAmbar); robot.setLED(2, colorAmbar)
                    else:
                        robot.setLED(1, colorApagado); robot.setLED(2, colorApagado)
                    robot.setLED(0, colorApagado); robot.setLED(3, colorApagado)

                elif valorDerecha < valorIzquierda:
                    robot.motorOn("l", "r", 20)
                    robot.motorOn("r", "f", 20)
                    if parpadeoActivo:
                        robot.setLED(0, colorAmbar); robot.setLED(3, colorAmbar)
                    else:
                        robot.setLED(0, colorApagado); robot.setLED(3, colorApagado)
                    robot.setLED(1, colorApagado); robot.setLED(2, colorApagado)
            else:
                robot.motorOn("l", "f", 20)
                robot.motorOn("r", "f", 20)
                ponerColorLeds(colorApagado)

    elif estado == "ATRAS":
        ponerColorLeds(colorApagado)

        distancia = robot.getDistance("r")

        if 0 < distancia <= 15:
            robot.motorOn("l", "f", 20)
            robot.motorOn("r", "r", 20)
        else:
            valorCentro = robot.getRawLFValue("c")
            valorIzquierda = robot.getRawLFValue("l")
            valorDerecha = robot.getRawLFValue("r")

            if valorCentro < 30000:
                if valorIzquierda < valorDerecha:
                    robot.motorOn("l", "f", 10)
                    robot.motorOn("r", "r", 10)
                elif valorDerecha < valorIzquierda:
                    robot.motorOn("l", "r", 10)
                    robot.motorOn("r", "f", 10)
            else:
                robot.motorOn("l", "r", 20)
                robot.motorOn("r", "r", 20)

    robot.show()
    sleep_ms(20)
