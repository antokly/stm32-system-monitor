"""
simple_test.py - Test minimal de la liaison PC <-> STM32 (via ESP32-C3 ou ST-LINK)

Usage :
    pip install pyserial
    python simple_test.py COM5 ping
    python simple_test.py COM5 temp
"""
import struct
import sys
import time

import serial

SOF, EOF = 0xAA, 0x55
CMD_PING = 0x01
CMD_GET_TEMP = 0x02


def crc8(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def build_frame(cmd_id: int, payload: bytes = b"") -> bytes:
    body = bytes([cmd_id, len(payload)]) + payload
    return bytes([SOF]) + body + bytes([crc8(body), EOF])


def read_frame(ser, timeout=1.5):
    """Lit une trame complète. Retourne (cmd_id, payload) ou None."""
    deadline = time.monotonic() + timeout
    buf = bytearray()
    while time.monotonic() < deadline:
        buf += ser.read(ser.in_waiting or 1)
        # cherche un SOF puis vérifie si la trame est complète
        while SOF in buf:
            start = buf.index(SOF)
            del buf[:start]
            if len(buf) < 3:
                break
            length = buf[2]
            total = 3 + length + 2
            if len(buf) < total:
                break
            frame = bytes(buf[:total])
            del buf[:total]
            if frame[-1] == EOF and crc8(frame[1:-2]) == frame[-2]:
                return frame[1], frame[3:3 + length]
            print("Trame invalide ignorée :", frame.hex(" "))
    return None


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
    action = sys.argv[2] if len(sys.argv) > 2 else "ping"
    cmd = {"ping": CMD_PING, "temp": CMD_GET_TEMP}[action]

    # DTR/RTS à False : évite de reset l'ESP32-C3 à l'ouverture du port
    ser = serial.Serial()
    ser.port, ser.baudrate, ser.timeout = port, 115200, 0.05
    ser.dtr = ser.rts = False
    ser.open()
    time.sleep(1.0)
    ser.reset_input_buffer()

    frame = build_frame(cmd)
    print("TX :", frame.hex(" "))
    ser.write(frame)

    resp = read_frame(ser)
    if resp is None:
        print("Pas de réponse (timeout)")
    else:
        cmd_id, payload = resp
        print(f"RX : cmd=0x{cmd_id:02X} payload={payload.hex(' ')}")
        if cmd_id == CMD_GET_TEMP and len(payload) == 4:
            print(f"Température : {struct.unpack('<f', payload)[0]:.1f} °C")
        elif cmd_id == CMD_PING:
            print("PING OK")
    ser.close()


if __name__ == "__main__":
    main()