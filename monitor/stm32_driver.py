"""
stm32_driver.py - Pilote Python pour le firmware STM32 (via passerelle ESP32-C3 ou ST-LINK)

Trame : [0xA5] [CMD] [LEN] [PAYLOAD...] [CRC8]
CRC8  : CRC-8/SMBUS (poly 0x07, init 0x00) sur CMD + LEN + PAYLOAD

    pip install pyserial
    python stm32_driver.py COM5 ping
    python stm32_driver.py COM5 temp | vbat | adc | all
    python stm32_driver.py COM5 pwm 1 45
"""
import struct
import sys
import time

SOF = 0xA5
MAX_PAYLOAD = 32

CMD_PING = 0x01
CMD_GET_TEMP = 0x02
CMD_GET_VBAT = 0x03
CMD_GET_ADC = 0x05
CMD_SET_PWM = 0x09
CMD_GET_ALL = 0x0A
CMD_ERROR = 0xFF

ERR_NAMES = {1: "commande inconnue", 2: "longueur invalide", 3: "paramètre invalide"}


class Stm32Error(Exception):
    """Le firmware a répondu CMD_ERROR."""


class Stm32Timeout(Stm32Error):
    """Pas de réponse dans le délai."""


def crc8(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def build_frame(cmd: int, payload: bytes = b"") -> bytes:
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"payload trop long (max {MAX_PAYLOAD})")
    body = bytes([cmd, len(payload)]) + payload
    return bytes([SOF]) + body + bytes([crc8(body)])


class Stm32:
    def __init__(self, port=None, baudrate=115200, timeout=1.5, ser=None):
        if ser is None:
            import serial
            ser = serial.Serial()
            ser.port, ser.baudrate, ser.timeout = port, baudrate, 0.05
            ser.dtr = ser.rts = False        # évite de reset l'ESP32-C3 à l'ouverture
            ser.open()
            time.sleep(1.0)                  # laisse la passerelle se stabiliser
        self.ser = ser
        self.timeout = timeout
        self._buf = bytearray()

    def close(self):
        self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------ bas niveau
    def _extract_frame(self):
        """Cherche une trame valide dans le buffer -> (cmd, payload) ou None."""
        buf = self._buf
        while True:
            if SOF not in buf:
                buf.clear()
                return None
            del buf[:buf.index(SOF)]
            if len(buf) < 3:
                return None
            length = buf[2]
            if length > MAX_PAYLOAD:
                del buf[0]                   # faux SOF : on se resynchronise
                continue
            total = length + 4               # SOF + CMD + LEN + PAYLOAD + CRC
            if len(buf) < total:
                return None
            frame = bytes(buf[:total])
            if crc8(frame[1:-1]) == frame[-1]:
                del buf[:total]
                return frame[1], frame[3:3 + length]
            del buf[0]

    def request(self, cmd: int, payload: bytes = b"") -> bytes:
        """Envoie une commande et retourne le payload de la réponse."""
        self.ser.reset_input_buffer()
        self._buf.clear()
        self.ser.write(build_frame(cmd, payload))

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            frame = self._extract_frame()
            if frame is None:
                self._buf += self.ser.read(self.ser.in_waiting or 1)
                continue
            rid, data = frame
            if rid == cmd:
                return data
            if rid == CMD_ERROR and data[:1] == bytes([cmd]):
                code = data[1] if len(data) > 1 else 0
                raise Stm32Error(f"commande 0x{cmd:02X} rejetée : {ERR_NAMES.get(code, code)}")
        raise Stm32Timeout(f"pas de réponse à la commande 0x{cmd:02X}")

    # ------------------------------------------------------------ commandes
    def ping(self) -> bool:
        self.request(CMD_PING)
        return True

    def get_temp(self) -> float:
        return struct.unpack("<f", self.request(CMD_GET_TEMP))[0]

    def get_vbat(self) -> float:
        return struct.unpack("<f", self.request(CMD_GET_VBAT))[0]

    def get_adc(self) -> tuple:
        return struct.unpack("<HHH", self.request(CMD_GET_ADC))

    def set_pwm(self, channel: int, duty_percent: int) -> None:
        if not 0 <= duty_percent <= 100:
            raise ValueError("duty doit être entre 0 et 100")
        self.request(CMD_SET_PWM, struct.pack("<BB", channel, duty_percent))

    def get_all(self) -> dict:
        temp, vbat, a0, a1, a2 = struct.unpack("<ffHHH", self.request(CMD_GET_ALL))
        return {"temp": temp, "vbat": vbat, "adc": [a0, a1, a2]}


# ---------------------------------------------------------------- CLI
def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    port, action, args = sys.argv[1], sys.argv[2], sys.argv[3:]
    with Stm32(port) as stm:
        try:
            if action == "ping":
                print("PING OK" if stm.ping() else "KO")
            elif action == "temp":
                print(f"Température : {stm.get_temp():.1f} °C")
            elif action == "vbat":
                print(f"VBat : {stm.get_vbat():.2f} V")
            elif action == "adc":
                print("ADC :", stm.get_adc())
            elif action == "all":
                print(stm.get_all())
            elif action == "pwm":
                stm.set_pwm(int(args[0]), int(args[1]))
                print("PWM OK")
            else:
                print("Commande inconnue :", action)
        except Stm32Error as e:
            print("Erreur :", e)


if __name__ == "__main__":
    main()