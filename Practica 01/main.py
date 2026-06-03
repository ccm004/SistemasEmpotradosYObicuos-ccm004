from PicoAutonomousRobotics import KitronikPicoRobotBuggy
from time import sleep_ms

enMarcha = False

robot = KitronikPicoRobotBuggy()


def ponerColorLeds(color):
    for indiceLed in range(4):
        robot.setLED(indiceLed, color)


def manejadorBoton(pinPulsado):
    global enMarcha
    if pinPulsado == robot.button:
        enMarcha = not enMarcha


robot.button.irq(trigger=machine.Pin.IRQ_RISING, handler=manejadorBoton)

ponerColorLeds(robot.PURPLE)
robot.show()

while True:
    if enMarcha == True:
        distanciaFrontal = robot.getDistance("f")
        distanciaTrasera = robot.getDistance("r")

        if (distanciaFrontal > 15):
            ponerColorLeds(robot.GREEN)
            robot.motorOn("l", "f", 85)
            robot.motorOn("r", "f", 85)

        elif (distanciaFrontal > 5):
            ponerColorLeds(robot.GREEN)
            robot.motorOff("l")
            robot.motorOff("r")
            if (distanciaTrasera > 15):
                ponerColorLeds(robot.BLUE)
                robot.motorOn("l", "r", 100)
                robot.motorOn("r", "r", 50)
                sleep_ms(100)
            else:
                ponerColorLeds(robot.YELLOW)
                robot.motorOn("l", "f", 100)
                robot.motorOn("r", "r", 100)
        else:
            ponerColorLeds(robot.RED)
            robot.motorOn("l", "r", 100)
            robot.motorOn("r", "f", 100)
        robot.show()
    else:
        robot.motorOff("l")
        robot.motorOff("r")
        ponerColorLeds(robot.PURPLE)
        robot.show()
    sleep_ms(50)
