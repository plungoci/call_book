"""Tests for the DX cluster line parser and the telnet client.

The client is exercised against a local socket server standing in for a
cluster node, so the suite stays offline and deterministic.
"""

from __future__ import annotations

import socket
import threading
import unittest
from datetime import UTC, datetime

from call_book.services.dx_cluster import (
    DxClusterClient,
    DxClusterError,
    _strip_telnet_commands,
    parse_spot,
)
from tests.support import require

NOW = datetime(2026, 9, 10, 18, 40, tzinfo=UTC)
LIVE_SPOT = "DX de HA8TKS:     14205.0  YO3ABC       Loud signal here               1832Z JN97"
SHOW_DX_SPOT = "   14205.0  YO3ABC       10-Sep-2026 1832Z  FT8 -12 dB           <HA8TKS>"


class ParseLiveSpotTests(unittest.TestCase):
    def test_all_fields_of_a_dx_de_line_are_read(self) -> None:
        spot = require(parse_spot(LIVE_SPOT, NOW))
        self.assertEqual(spot.dx_call, "YO3ABC")
        self.assertEqual(spot.spotter, "HA8TKS")
        self.assertEqual(spot.frequency_khz, 14205.0)
        self.assertAlmostEqual(spot.frequency_mhz, 14.205)
        self.assertEqual(spot.band, "20m")
        self.assertEqual(spot.comment, "Loud signal here")
        self.assertEqual(spot.locator, "JN97")
        self.assertEqual(spot.spotted_at_utc, datetime(2026, 9, 10, 18, 32, tzinfo=UTC))

    def test_a_spot_without_a_locator_is_still_parsed(self) -> None:
        spot = require(parse_spot("DX de EA5XXX:      7005.0  EA8ZZZ       CQ CQ      1234Z", NOW))
        self.assertEqual(spot.dx_call, "EA8ZZZ")
        self.assertEqual(spot.locator, "")
        self.assertEqual(spot.band, "40m")

    def test_a_portable_callsign_keeps_its_suffix(self) -> None:
        spot = require(parse_spot("DX de DL1ABC:    144300.0  YO2XYZ/P     tropo     1839Z", NOW))
        self.assertEqual(spot.dx_call, "YO2XYZ/P")
        self.assertEqual(spot.band, "2m")

    def test_a_time_just_after_midnight_belongs_to_the_previous_day(self) -> None:
        spot = require(parse_spot("DX de X:  7000.0  Y  c 2350Z", datetime(2026, 9, 11, 0, 5, tzinfo=UTC)))
        self.assertEqual(spot.spotted_at_utc, datetime(2026, 9, 10, 23, 50, tzinfo=UTC))

    def test_an_impossible_time_is_rejected(self) -> None:
        self.assertIsNone(parse_spot("DX de X:  7000.0  Y  c 9999Z", NOW))


class ParseShowDxTests(unittest.TestCase):
    def test_a_show_dx_row_carries_its_own_date(self) -> None:
        spot = require(parse_spot(SHOW_DX_SPOT, NOW))
        self.assertEqual(spot.dx_call, "YO3ABC")
        self.assertEqual(spot.spotter, "HA8TKS")
        self.assertEqual(spot.comment, "FT8 -12 dB")
        self.assertEqual(spot.spotted_at_utc, datetime(2026, 9, 10, 18, 32, tzinfo=UTC))

    def test_a_row_without_a_comment_is_parsed(self) -> None:
        spot = require(parse_spot("  3573.0  IK2ABC        6-Sep-2026 1200Z                       <DL1XYZ>", NOW))
        self.assertEqual(spot.comment, "")
        self.assertEqual(spot.band, "80m")

    def test_an_unknown_month_is_rejected(self) -> None:
        self.assertIsNone(parse_spot("  3573.0  IK2ABC  6-Zzz-2026 1200Z  x  <DL1XYZ>", NOW))


class NonSpotLineTests(unittest.TestCase):
    def test_banners_bulletins_and_blank_lines_are_ignored(self) -> None:
        for line in (
            "",
            "   ",
            "Hello and welcome to the cluster",
            "WWV de W0MU <18Z> :   SFI=142, A=7, K=2",
            "YO3ABC de HA8TKS: chat message",
        ):
            self.assertIsNone(parse_spot(line, NOW), line)


class TelnetNegotiationTests(unittest.TestCase):
    def test_iac_sequences_are_removed(self) -> None:
        self.assertEqual(_strip_telnet_commands(b"\xff\xfd\x18hello"), b"hello")

    def test_subnegotiation_blocks_are_removed(self) -> None:
        self.assertEqual(_strip_telnet_commands(b"a\xff\xfa\x1f\x00\x50\xf0b"), b"ab")

    def test_an_escaped_literal_byte_is_kept(self) -> None:
        self.assertEqual(_strip_telnet_commands(b"a\xff\xffb"), b"a\xffb")

    def test_plain_text_is_untouched(self) -> None:
        self.assertEqual(_strip_telnet_commands(b"plain text"), b"plain text")


class FakeNode:
    """A minimal stand-in for a cluster node, on a loopback port."""

    def __init__(self, script: list[bytes], prompt: bytes = b"Please enter your call: "):
        self.script = script
        self.prompt = prompt
        self.received = b""
        self._server = socket.socket()
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(1)
        self.port = self._server.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        try:
            connection, _ = self._server.accept()
        except OSError:
            return
        with connection:
            connection.sendall(self.prompt)
            try:
                self.received = connection.recv(256)
                for line in self.script:
                    connection.sendall(line + b"\r\n")
            except OSError:
                pass

    def close(self) -> None:
        self._server.close()
        self._thread.join(timeout=2)


class ClientTests(unittest.TestCase):
    def test_the_client_logs_in_and_yields_the_spots_that_follow(self) -> None:
        node = FakeNode([LIVE_SPOT.encode(), b"random chatter", SHOW_DX_SPOT.encode()])
        self.addCleanup(node.close)
        client = DxClusterClient("127.0.0.1", node.port, "YO3TEST", request_recent=False)
        client.connect()
        self.addCleanup(client.close)
        spots = []
        for spot in client.spots():
            spots.append(spot)
            if len(spots) == 2:
                break
        self.assertEqual([spot.dx_call for spot in spots], ["YO3ABC", "YO3ABC"])
        self.assertIn(b"YO3TEST", node.received)

    def test_connecting_without_a_callsign_is_refused_before_any_socket_is_opened(self) -> None:
        with self.assertRaises(DxClusterError):
            DxClusterClient("127.0.0.1", 1, "").connect()

    def test_an_unreachable_node_raises_a_readable_error(self) -> None:
        # Port 1 on loopback: nothing listens there, so the connection is
        # refused immediately rather than hanging.
        client = DxClusterClient("127.0.0.1", 1, "YO3TEST")
        with self.assertRaises(DxClusterError) as error:
            client.connect()
        self.assertIn("127.0.0.1:1", str(error.exception))

    def test_a_node_closing_the_connection_ends_the_iteration_with_an_error(self) -> None:
        node = FakeNode([LIVE_SPOT.encode()])
        self.addCleanup(node.close)
        client = DxClusterClient("127.0.0.1", node.port, "YO3TEST", request_recent=False)
        client.connect()
        self.addCleanup(client.close)
        with self.assertRaises(DxClusterError):
            list(client.spots())

    def test_close_stops_the_iteration_without_raising(self) -> None:
        node = FakeNode([LIVE_SPOT.encode()])
        self.addCleanup(node.close)
        client = DxClusterClient("127.0.0.1", node.port, "YO3TEST", request_recent=False)
        client.connect()
        spots = client.spots()
        self.assertEqual(next(spots).dx_call, "YO3ABC")
        client.close()
        self.assertEqual(list(spots), [])

    def test_closing_twice_is_harmless(self) -> None:
        client = DxClusterClient("127.0.0.1", 1, "YO3TEST")
        client.close()
        client.close()
