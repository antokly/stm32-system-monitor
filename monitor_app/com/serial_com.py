import serial
import time

class SerialCommunication:
    def __init__(self, port=None, baudrate=115200, timeout=1.5, ser=None):
        if ser is None:
            ser = serial.Serial()
            ser.port, ser.baudrate, ser.timeout = port, baudrate, 0.05
            ser.dtr = False
            ser.rts = False
            ser.open()
            time.sleep(1.0) # UART USB Bridge needs some time to stabilize
        self.ser = ser
        self.timeout = timeout
        self.input_buf = bytearray()

    def close(self):
        self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()