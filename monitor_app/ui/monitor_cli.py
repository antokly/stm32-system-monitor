import sys
from com.serial_com import SerialCommunication
from com.protocol import Protocol, CommError
from com.commands import Command

def main_cli():

    # CLI parse args
    if len(sys.argv) < 3:
        print(__doc__)
        return
    port, action, args = sys.argv[1], sys.argv[2], sys.argv[3:]

    serial_com = SerialCommunication(port)
    protocol = Protocol(serial_com)
    command = Command(protocol)

    try:
        if action == "ping":
            print("PING OK" if command.ping() else "KO")
        elif action == "temp":
            print(f"Température : {command.get_temp():.1f} °C")
        elif action == "vbat":
            print(f"VBat : {command.get_vbat():.2f} V")
        elif action == "adc":
            print("ADC :", command.get_adc())
        elif action == "all":
            print(command.get_all())
        elif action == "pwm":
            command.set_pwm(int(args[0]), int(args[1]))
            print("PWM OK")
        else:
            print("Commande inconnue :", action)
    except CommError as e:
        print("Erreur :", e)
