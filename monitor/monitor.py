"""
uart_link.py - Couche de communication PC <-> STM32 (via passerelle ESP32-C3 transparente)

Trame : [SOF 0xAA] [CMD_ID] [LEN] [PAYLOAD...] [CRC8] [EOF 0x55]
CRC8  : poly 0x07, init 0x00, calculé sur CMD_ID + LEN + PAYLOAD

Couches :
    Transport (SerialTransport / TcpTransport)   -> octets bruts
    FrameParser                                  -> octets -> Frame (machine à états)
    UartLink                                     -> request/réponse, événements, reconnexion
"""
from __future__ import annotations

import queue
import socket
import struct
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional

# --------------------------------------------------------------------------- #
# Constantes (à garder synchronisées avec protocol.h)
# --------------------------------------------------------------------------- #
SOF = 0xAA
EOF = 0x55
MAX_PAYLOAD = 28

CMD_PING = 0x01
CMD_GET_TEMP = 0x02
CMD_GET_VBAT = 0x03
CMD_GET_ADC = 0x05
CMD_SET_PWM = 0x09
CMD_GET_ALL = 0x0A
CMD_ERROR = 0xFF

# Plage réservée aux commandes interceptées par la passerelle ESP32-C3
GATEWAY_CMD_MIN = 0xF0
GATEWAY_CMD_MAX = 0xFE


def is_gateway_cmd(cmd_id: int) -> bool:
    return GATEWAY_CMD_MIN <= cmd_id <= GATEWAY_CMD_MAX


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class LinkError(Exception):
    """Erreur générique de liaison (port fermé, déconnexion...)."""


class LinkTimeout(LinkError):
    """Aucune réponse du STM32 dans le délai imparti."""


class DeviceError(LinkError):
    """Le STM32 a répondu CMD_ERROR pour la commande envoyée."""

    def __init__(self, cmd_id: int):
        super().__init__(f"Le firmware a rejeté la commande 0x{cmd_id:02X}")
        self.cmd_id = cmd_id


# --------------------------------------------------------------------------- #
# CRC8 + encodage
# --------------------------------------------------------------------------- #
def crc8(data: bytes) -> int:
    crc = 0x00
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def encode_frame(cmd_id: int, payload: bytes = b"") -> bytes:
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"Payload trop long ({len(payload)} > {MAX_PAYLOAD})")
    body = bytes([cmd_id, len(payload)]) + payload
    return bytes([SOF]) + body + bytes([crc8(body), EOF])


@dataclass
class Frame:
    cmd_id: int
    payload: bytes = b""
    timestamp: float = field(default_factory=time.monotonic)

    def __repr__(self) -> str:
        return f"Frame(cmd=0x{self.cmd_id:02X}, payload={self.payload.hex(' ')})"


# --------------------------------------------------------------------------- #
# Parseur de trames (indépendant du transport, facilement testable)
# --------------------------------------------------------------------------- #
class FrameParser:
    _WAIT_SOF, _WAIT_CMD, _WAIT_LEN, _WAIT_PAYLOAD, _WAIT_CRC, _WAIT_EOF = range(6)

    def __init__(self, inter_byte_timeout: float = 0.3):
        self.inter_byte_timeout = inter_byte_timeout
        self.crc_errors = 0
        self.framing_errors = 0
        self.timeout_errors = 0
        self.frames_ok = 0
        self.reset()

    def reset(self) -> None:
        self._state = self._WAIT_SOF
        self._cmd = 0
        self._len = 0
        self._payload = bytearray()
        self._crc = 0
        self._last_byte_time = time.monotonic()

    def feed(self, data: bytes, now: Optional[float] = None) -> list[Frame]:
        """Consomme des octets (n'importe quel découpage) et retourne les trames complètes."""
        now = time.monotonic() if now is None else now
        # Trame restée incomplète trop longtemps -> on abandonne et on se resynchronise
        if self._state != self._WAIT_SOF and now - self._last_byte_time > self.inter_byte_timeout:
            self.timeout_errors += 1
            self.reset()
        self._last_byte_time = now

        frames: list[Frame] = []
        for b in data:
            if self._state == self._WAIT_SOF:
                if b == SOF:
                    self._state = self._WAIT_CMD

            elif self._state == self._WAIT_CMD:
                self._cmd = b
                self._state = self._WAIT_LEN

            elif self._state == self._WAIT_LEN:
                if b > MAX_PAYLOAD:
                    self.framing_errors += 1
                    self._state = self._WAIT_SOF
                else:
                    self._len = b
                    self._payload = bytearray()
                    self._state = self._WAIT_PAYLOAD if b else self._WAIT_CRC

            elif self._state == self._WAIT_PAYLOAD:
                self._payload.append(b)
                if len(self._payload) >= self._len:
                    self._state = self._WAIT_CRC

            elif self._state == self._WAIT_CRC:
                self._crc = b
                self._state = self._WAIT_EOF

            elif self._state == self._WAIT_EOF:
                if b != EOF:
                    self.framing_errors += 1
                elif crc8(bytes([self._cmd, self._len]) + bytes(self._payload)) != self._crc:
                    self.crc_errors += 1
                else:
                    self.frames_ok += 1
                    frames.append(Frame(self._cmd, bytes(self._payload), now))
                self._state = self._WAIT_SOF
        return frames


# --------------------------------------------------------------------------- #
# Transports
# --------------------------------------------------------------------------- #
class Transport(ABC):
    """Interface minimale : tout ce qui sait lire/écrire des octets."""

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def write(self, data: bytes) -> None: ...

    @abstractmethod
    def read(self) -> bytes:
        """Retourne les octets disponibles, ou b'' après un court timeout.
        Doit lever une exception si la liaison est perdue."""

    @property
    @abstractmethod
    def is_open(self) -> bool: ...


class SerialTransport(Transport):
    """Port série / USB CDC (ESP32-C3). DTR/RTS maintenus bas pour éviter
    un reset ou le mode download du C3 à l'ouverture du port."""

    def __init__(self, port: str, baudrate: int = 115200, open_delay: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.open_delay = open_delay  # laisse le C3 se stabiliser après ouverture
        self._ser = None

    def open(self) -> None:
        import serial  # import local : pyserial n'est requis que pour ce transport

        ser = serial.Serial()
        ser.port = self.port
        ser.baudrate = self.baudrate
        ser.timeout = 0.05
        ser.write_timeout = 1.0
        ser.dtr = False
        ser.rts = False
        ser.open()
        time.sleep(self.open_delay)
        ser.reset_input_buffer()
        self._ser = ser

    def close(self) -> None:
        if self._ser:
            try:
                self._ser.close()
            finally:
                self._ser = None

    def write(self, data: bytes) -> None:
        self._ser.write(data)
        self._ser.flush()

    def read(self) -> bytes:
        # Bloque max 50 ms sur le 1er octet, puis récupère tout ce qui est arrivé
        data = self._ser.read(1)
        if data:
            data += self._ser.read(self._ser.in_waiting)
        return data

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open


class TcpTransport(Transport):
    """Même protocole sur TCP (passerelle ESP32-C3 en Wi-Fi, ex. pont TCP<->UART)."""

    def __init__(self, host: str, port: int):
        self.host, self.port = host, port
        self._sock: Optional[socket.socket] = None

    def open(self) -> None:
        self._sock = socket.create_connection((self.host, self.port), timeout=3.0)
        self._sock.settimeout(0.05)

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def write(self, data: bytes) -> None:
        self._sock.sendall(data)

    def read(self) -> bytes:
        try:
            data = self._sock.recv(256)
        except socket.timeout:
            return b""
        if data == b"":
            raise ConnectionError("Connexion TCP fermée par le pair")
        return data

    @property
    def is_open(self) -> bool:
        return self._sock is not None


# --------------------------------------------------------------------------- #
# Liaison haut niveau
# --------------------------------------------------------------------------- #
class UartLink:
    """
    - Thread de lecture dédié (ne bloque jamais l'UI)
    - request() : envoi + attente de la réponse correspondante (1 requête à la fois)
    - Trames non sollicitées -> events (queue) et/ou callback on_event
    - Détection de déconnexion -> callback on_connection_change(bool)
    """

    def __init__(
        self,
        transport: Transport,
        response_timeout: float = 1.5,
        retries: int = 1,
        on_event: Optional[Callable[[Frame], None]] = None,
        on_connection_change: Optional[Callable[[bool], None]] = None,
    ):
        self.transport = transport
        self.response_timeout = response_timeout
        self.retries = retries  # attention : un retry rejoue la commande (OK pour GET_*/SET idempotents)
        self.on_event = on_event
        self.on_connection_change = on_connection_change

        self.parser = FrameParser()
        self.events: "queue.Queue[Frame]" = queue.Queue(maxsize=1000)
        self.timeouts = 0

        self._resp_queue: "queue.Queue[Frame]" = queue.Queue()
        self._expected: Optional[int] = None
        self._req_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._connected = False

    # -- cycle de vie ------------------------------------------------------- #
    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        """Ouvre le transport et démarre le thread de lecture. Rappelable après une déconnexion."""
        self.close()
        self.transport.open()
        self.parser.reset()
        self._stop.clear()
        self._thread = threading.Thread(target=self._read_loop, name="uart-rx", daemon=True)
        self._thread.start()
        self._set_connected(True)

    def close(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        self._thread = None
        self.transport.close()
        self._set_connected(False)

    def __enter__(self) -> "UartLink":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _set_connected(self, state: bool) -> None:
        if state != self._connected:
            self._connected = state
            if self.on_connection_change:
                self.on_connection_change(state)

    # -- thread de lecture -------------------------------------------------- #
    def _read_loop(self) -> None:
        while not self._stop.is_set():
            try:
                data = self.transport.read()
            except Exception:
                # Câble débranché, passerelle reset, socket fermée...
                self._set_connected(False)
                return
            if not data:
                continue
            for frame in self.parser.feed(data):
                self._dispatch(frame)

    def _dispatch(self, frame: Frame) -> None:
        expected = self._expected
        if expected is not None and (frame.cmd_id == expected or frame.cmd_id == CMD_ERROR):
            self._resp_queue.put(frame)
            return
        try:
            self.events.put_nowait(frame)
        except queue.Full:
            pass  # on préfère perdre un événement que bloquer la lecture
        if self.on_event:
            self.on_event(frame)

    # -- API requête/réponse ------------------------------------------------ #
    def send(self, cmd_id: int, payload: bytes = b"") -> None:
        if not self._connected:
            raise LinkError("Liaison non connectée")
        try:
            self.transport.write(encode_frame(cmd_id, payload))
        except Exception as e:
            self._set_connected(False)
            raise LinkError(f"Échec d'écriture : {e}") from e

    def request(self, cmd_id: int, payload: bytes = b"", timeout: Optional[float] = None) -> Frame:
        """Envoie une commande et retourne la trame de réponse.
        Lève LinkTimeout, DeviceError ou LinkError."""
        timeout = self.response_timeout if timeout is None else timeout
        with self._req_lock:
            for attempt in range(self.retries + 1):
                self._drain(self._resp_queue)
                self._expected = cmd_id
                try:
                    self.send(cmd_id, payload)
                    deadline = time.monotonic() + timeout
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise queue.Empty
                        frame = self._resp_queue.get(timeout=remaining)
                        if frame.cmd_id == cmd_id:
                            return frame
                        # CMD_ERROR : payload[0] = cmd_id fautif
                        if frame.payload[:1] == bytes([cmd_id]):
                            raise DeviceError(cmd_id)
                except queue.Empty:
                    self.timeouts += 1
                    if attempt == self.retries:
                        raise LinkTimeout(f"Pas de réponse à 0x{cmd_id:02X} après {attempt + 1} essai(s)")
                finally:
                    self._expected = None
        raise LinkTimeout  # inatteignable, pour les linters

    @staticmethod
    def _drain(q: "queue.Queue") -> None:
        while True:
            try:
                q.get_nowait()
            except queue.Empty:
                return

    # -- helpers métier ----------------------------------------------------- #
    def ping(self) -> bool:
        try:
            self.request(CMD_PING)
            return True
        except LinkError:
            return False

    def get_temp(self) -> float:
        return struct.unpack("<f", self.request(CMD_GET_TEMP).payload)[0]

    def set_pwm(self, channel: int, duty: int) -> None:
        self.request(CMD_SET_PWM, struct.pack("<BB", channel, duty))

    def stats(self) -> dict:
        p = self.parser
        return {
            "frames_ok": p.frames_ok,
            "crc_errors": p.crc_errors,
            "framing_errors": p.framing_errors,
            "rx_timeouts": p.timeout_errors,
            "request_timeouts": self.timeouts,
        }


# --------------------------------------------------------------------------- #
# Démo : python uart_link.py COM4
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
    link = UartLink(
        SerialTransport(port),
        on_connection_change=lambda ok: print("[LINK]", "connecté" if ok else "déconnecté"),
    )
    with link:
        print("PING :", "OK" if link.ping() else "pas de réponse")
        try:
            while link.connected:
                print(f"Température : {link.get_temp():.1f} °C")
                time.sleep(0.5)
        except LinkError as e:
            print("Erreur :", e)
        except KeyboardInterrupt:
            pass
        print(link.stats())