import time

SOF = 0xA5
MAX_PAYLOAD = 32
CMD_ERROR = 0xFF
ERR_NAMES = {1: "commande inconnue", 2: "longueur invalide", 3: "paramètre invalide"}

def crc8(data: bytes) -> int: # Compute crc8 with generator polynomial 0x07
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

class Protocol:
    def __init__(self, serial_com):
        self.serial_comm = serial_com

    def receive_frame(self):
        """ receive frame from input buffer -> (cmd, payload) or None."""
        buf = self.serial_comm.input_buf
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

    def send_command(self, cmd: int, payload: bytes = b"") -> bytes:
        """send a request and return payload of the response."""
        self.serial_comm.ser.reset_input_buffer()
        self.serial_comm.input_buf.clear()
        self.serial_comm.ser.write(build_frame(cmd, payload))

        timeout_com = time.monotonic() + self.serial_comm.timeout
        while time.monotonic() < timeout_com:
            frame = self.receive_frame()
            if frame is None:
                self.serial_comm.input_buf += self.serial_comm.ser.read(self.serial_comm.ser.in_waiting or 1)
                continue
            cmd_id, data = frame
            if cmd_id == cmd:
                return data
            if cmd_id == CMD_ERROR and data[:1] == bytes([cmd]):
                code = data[1] if len(data) > 1 else 0
                raise CommError(f"commande 0x{cmd:02X} rejetée : {ERR_NAMES.get(code, code)}")
        raise CommTimeout(f"pas de réponse à la commande 0x{cmd:02X}")

class CommError(Exception):
    """Le firmware a répondu CMD_ERROR."""

class CommTimeout(CommError):
    """Pas de réponse dans le délai."""