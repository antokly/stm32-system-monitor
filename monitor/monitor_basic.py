import serial, time

ser = serial.Serial("COM4", 115200, timeout=0.1)  # ou /dev/ttyACM0
time.sleep(0.5)  # laisse le temps à l'USB-CDC de s'initialiser

ser.write(b"ma_commande\n")

# Lire la réponse pendant ~1 s
t0 = time.time()
while time.time() - t0 < 1.0:
    line = ser.readline()
    if line:
        print(line.decode(errors="replace").rstrip())