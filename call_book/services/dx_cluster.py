"""Client for a DX cluster node, and the parser for the spot lines it sends.

A DX cluster is a plain TCP ("telnet") service: nodes running DXSpider,
AR-Cluster or CC-Cluster announce every spot their users report, one line of
text at a time. That protocol is what web front-ends such as
https://dxcluster.ha8tks.hu/hamgeocoding/ read as well; this module speaks it
directly, so the logbook needs no web service, no API key and no account
beyond the operator's own callsign, which is what a node asks for at login.

Two line formats are understood:

  ``DX de HA8TKS:     14205.0  YO3ABC   Loud here      1832Z JN97``
      a live announcement, pushed as it happens.

  ``  14205.0  YO3ABC   10-Sep-2026 1832Z  Loud here   <HA8TKS>``
      a row of the node's reply to ``sh/dx``, used to fill the table with
      recent spots at connect time instead of starting empty.

Anything else the node sends (banners, chat, WWV bulletins) is ignored.
"""

from __future__ import annotations

import logging
import re
import socket
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ..validators import band_for_frequency

LOG = logging.getLogger(__name__)

DEFAULT_HOST = "dxfun.com"
DEFAULT_PORT = 8000
CONNECT_TIMEOUT_SECONDS = 15
# Long enough that a quiet band doesn't look like a dropped connection, short
# enough that closing the panel doesn't hang waiting on a silent socket.
READ_TIMEOUT_SECONDS = 90
RECENT_SPOTS_COMMAND = "sh/dx 30"

_LOGIN_PROMPTS = ("login", "call", "callsign", "indicativ", "please enter")

_DX_DE_RE = re.compile(
    r"^DX\s+de\s+(?P<spotter>[A-Z0-9/\-]+?):?\s+"
    r"(?P<khz>\d{2,9}(?:\.\d+)?)\s+"
    r"(?P<dx>[A-Z0-9/]+)\s*"
    r"(?P<comment>.*?)\s*"
    r"(?P<time>\d{4})Z"
    r"(?:\s+(?P<locator>[A-R]{2}\d{2}(?:[A-X]{2})?))?\s*$",
    re.IGNORECASE,
)
_SHOW_DX_RE = re.compile(
    r"^\s*(?P<khz>\d{2,9}(?:\.\d+)?)\s+"
    r"(?P<dx>[A-Z0-9/]+)\s+"
    r"(?P<date>\d{1,2}-[A-Za-z]{3}-\d{4})\s+"
    r"(?P<time>\d{4})Z\s*"
    r"(?P<comment>.*?)\s*"
    r"<(?P<spotter>[A-Z0-9/\-]+)>\s*$",
    re.IGNORECASE,
)
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip


class DxClusterError(RuntimeError):
    """The node could not be reached, or dropped the connection."""


@dataclass(frozen=True, slots=True)
class DxSpot:
    """One announced spot, as sent by the cluster."""

    dx_call: str
    frequency_khz: float
    spotter: str
    comment: str
    spotted_at_utc: datetime
    locator: str = ""

    @property
    def frequency_mhz(self) -> float:
        return self.frequency_khz / 1000.0

    @property
    def band(self) -> str:
        return band_for_frequency(self.frequency_mhz)

    @property
    def key(self) -> tuple[str, float, str]:
        """Identity used to drop the duplicates a node repeats within seconds."""
        return (self.dx_call, round(self.frequency_khz, 1), self.spotter)


def _spot_time(hhmm: str, now: datetime) -> datetime:
    """Turn a bare HHMM from the node into a UTC timestamp near ``now``.

    Live spots carry no date. A time that looks like it is in the future is
    read as belonging to the previous day, which is what happens for the few
    minutes around midnight UTC and for a node whose clock runs slightly slow.
    """
    hours, minutes = int(hhmm[:2]), int(hhmm[2:])
    if hours > 23 or minutes > 59:
        raise ValueError(f"Oră invalidă în spot: {hhmm!r}")
    stamp = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    if stamp - now > timedelta(minutes=10):
        stamp -= timedelta(days=1)
    return stamp


def _full_date(date_text: str, hhmm: str) -> datetime:
    day, month_name, year = date_text.split("-")
    month = _MONTHS.get(month_name.lower())
    if month is None:
        raise ValueError(f"Lună necunoscută în spot: {month_name!r}")
    return datetime(int(year), month, int(day), int(hhmm[:2]), int(hhmm[2:]), tzinfo=UTC)


def parse_spot(line: str, now: datetime | None = None) -> DxSpot | None:
    """Return the spot a cluster line announces, or ``None`` for any other line."""
    text = line.strip()
    if not text:
        return None
    now = now or datetime.now(UTC)
    match = _DX_DE_RE.match(text)
    if match:
        try:
            spotted_at = _spot_time(match.group("time"), now)
            frequency = float(match.group("khz"))
        except ValueError:
            return None
        return DxSpot(
            match.group("dx").upper(),
            frequency,
            match.group("spotter").upper(),
            match.group("comment").strip(),
            spotted_at,
            (match.group("locator") or "").upper(),
        )
    match = _SHOW_DX_RE.match(text)
    if match:
        try:
            spotted_at = _full_date(match.group("date"), match.group("time"))
            frequency = float(match.group("khz"))
        except ValueError:
            return None
        return DxSpot(
            match.group("dx").upper(),
            frequency,
            match.group("spotter").upper(),
            match.group("comment").strip(),
            spotted_at,
        )
    return None


def _strip_telnet_commands(data: bytes) -> bytes:
    """Remove IAC negotiation sequences some nodes send before the banner."""
    if b"\xff" not in data:
        return data
    output = bytearray()
    index = 0
    while index < len(data):
        byte = data[index]
        if byte != 0xFF:
            output.append(byte)
            index += 1
            continue
        # IAC IAC is a literal 0xFF; IAC SB ... SE is a subnegotiation; every
        # other IAC command is three bytes long.
        if index + 1 < len(data) and data[index + 1] == 0xFF:
            output.append(0xFF)
            index += 2
        elif index + 1 < len(data) and data[index + 1] == 0xFA:
            end = data.find(b"\xf0", index)
            index = len(data) if end == -1 else end + 1
        else:
            index += 3
    return bytes(output)


class DxClusterClient:
    """A line-oriented connection to one DX cluster node.

    Usage is single-pass: ``connect()``, iterate ``spots()``, then ``close()``.
    ``close()`` is deliberately safe to call from another thread — it shuts the
    socket down so a blocked read returns and the iteration ends, which is how
    the UI stops the background reader without waiting for the next spot.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        callsign: str = "",
        request_recent: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.callsign = callsign.strip().upper()
        self.request_recent = request_recent
        self._socket: socket.socket | None = None
        self._buffer = b""
        self._closed = False

    def connect(self) -> None:
        if not self.callsign:
            raise DxClusterError("Nodul DX cluster cere un indicativ: completează-l în Setări → Date operator.")
        try:
            self._socket = socket.create_connection((self.host, self.port), timeout=CONNECT_TIMEOUT_SECONDS)
        except (TimeoutError, OSError) as exc:
            raise DxClusterError(f"Nu m-am putut conecta la {self.host}:{self.port}.") from exc
        self._socket.settimeout(READ_TIMEOUT_SECONDS)

    def _send(self, command: str) -> None:
        if self._socket is None:
            raise DxClusterError("Conexiunea la nodul DX cluster nu este deschisă.")
        try:
            self._socket.sendall(f"{command}\r\n".encode())
        except OSError as exc:
            raise DxClusterError("Conexiunea către nodul DX cluster s-a întrerupt.") from exc

    def _read_lines(self) -> Iterator[str]:
        """Yield decoded lines, including a trailing prompt with no newline.

        Nodes are not consistent about line endings and a login prompt arrives
        without one at all, so the buffer is also yielded when it looks like a
        prompt — otherwise login would block until the node gave up.
        """
        if self._socket is None:
            raise DxClusterError("Conexiunea la nodul DX cluster nu este deschisă.")
        while not self._closed:
            try:
                chunk = self._socket.recv(4096)
            except TimeoutError as exc:
                raise DxClusterError("Nodul DX cluster nu a mai trimis date.") from exc
            except OSError as exc:
                if self._closed:
                    return
                raise DxClusterError("Conexiunea către nodul DX cluster s-a întrerupt.") from exc
            if not chunk:
                if self._closed:
                    return
                raise DxClusterError("Nodul DX cluster a închis conexiunea.")
            self._buffer += _strip_telnet_commands(chunk)
            while b"\n" in self._buffer:
                raw, self._buffer = self._buffer.split(b"\n", 1)
                yield raw.decode("utf-8", "replace").replace("\r", "").rstrip()
            pending = self._buffer.decode("utf-8", "replace").strip().lower()
            if pending and any(prompt in pending for prompt in _LOGIN_PROMPTS):
                self._buffer = b""
                yield pending

    def spots(self) -> Iterator[DxSpot]:
        """Log in if asked to, then yield every spot until the connection ends."""
        logged_in = False
        for line in self._read_lines():
            if not logged_in and any(prompt in line.lower() for prompt in _LOGIN_PROMPTS):
                self._send(self.callsign)
                logged_in = True
                if self.request_recent:
                    self._send(RECENT_SPOTS_COMMAND)
                continue
            spot = parse_spot(line)
            if spot is not None:
                yield spot

    def close(self) -> None:
        """Stop the iteration; safe to call from another thread, and twice."""
        self._closed = True
        if self._socket is not None:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                LOG.debug("Socketul DX cluster era deja închis.", exc_info=True)
            self._socket.close()
            self._socket = None
