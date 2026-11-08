import struct

CMD_PING = 0x01
CMD_GET_TEMP = 0x02
CMD_GET_VBAT = 0x03
CMD_GET_ADC = 0x05
CMD_SET_PWM = 0x09
CMD_GET_ALL = 0x0A
CMD_ERROR = 0xFF

class Command:
    def __init__(self, protocol):
        self.protocol = protocol

    def ping(self) -> bool:
        self.protocol.send_command(CMD_PING)
        return True

    def get_temp(self) -> float:
        return struct.unpack("<f", self.protocol.send_command(CMD_GET_TEMP))[0]

    def get_vbat(self) -> float:
        return struct.unpack("<f", self.protocol.send_command(CMD_GET_VBAT))[0]

    def get_adc(self) -> tuple:
        return struct.unpack("<HHH", self.protocol.send_command(CMD_GET_ADC))

    def set_pwm(self, channel: int, duty_percent: int) -> None:
        if not 0 <= duty_percent <= 100:
            raise ValueError("duty doit être entre 0 et 100")
        self.protocol.send_command(CMD_SET_PWM, struct.pack("<BB", channel, duty_percent))

    def get_all(self) -> dict:
        temp, vbat, a0, a1, a2 = struct.unpack("<ffHHH", self.protocol.send_command(CMD_GET_ALL))
        return {"temp": temp, "vbat": vbat, "adc": [a0, a1, a2]}