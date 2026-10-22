# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""Native LINK interoperability and hostile-input checks using real TCP sockets."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import socket
import subprocess
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import link_server as link


class NativeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="link-native-")
        self.root = Path(self.temporary.name) / "worlds"
        self.world = self.root / "hello-world"
        self.world.mkdir(parents=True)
        self.manifest = b'world { version: "0.1"; id: "hello-world"; }\n'
        (self.world / "world.link").write_bytes(self.manifest)
        (self.world / "scene.element").write_bytes(b"scene {}\n")
        (self.world / "assets").mkdir()
        (self.world / "assets" / "연결.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
        sibling = self.root / "second-world"
        sibling.mkdir()
        (sibling / "world.link").write_bytes(b"other world")
        self.server = link.create_server("127.0.0.1", 0, self.root)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def connect(self):
        connection = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        connection.settimeout(2)
        self.addCleanup(connection.close)
        return connection

    def frame(self, kind, request_id=0, payload=b"", **kwargs):
        return link.HEADER.pack(kwargs.get("magic", b"LINK"), kwargs.get("major", 0), kwargs.get("minor", 1),
                                kind, kwargs.get("flags", 0), request_id, kwargs.get("size", len(payload))) + payload

    def receive(self, connection):
        header = link.receive_exact(connection, link.HEADER.size, time.monotonic() + 2)
        magic, major, minor, kind, flags, request_id, size = link.HEADER.unpack(header)
        self.assertEqual((magic, major, minor, flags), (b"LINK", 0, 1, 0))
        self.assertLessEqual(size, link.IMAGE_LIMIT)
        return kind, request_id, link.receive_exact(connection, size, time.monotonic() + 2)

    def hello(self, connection=None, world=b"hello-world"):
        connection = connection or self.connect()
        payload = b"\x00\x01" + world
        connection.sendall(self.frame(link.MESSAGE_HELLO, 0, payload))
        self.assertEqual(self.receive(connection), (link.MESSAGE_WELCOME, 0, payload))
        return connection

    def get(self, connection, path, request_id=1, maximum=16 * 1024 * 1024):
        path = path.encode("utf-8") if isinstance(path, str) else path
        connection.sendall(self.frame(link.MESSAGE_GET, request_id, struct.pack("!I", maximum) + path))
        return self.receive(connection)

    def assert_closed(self, connection):
        try:
            self.assertEqual(connection.recv(1), b"")
        except ConnectionResetError:
            pass

    def assert_error(self, connection, code, request_id=0):
        kind, actual_id, payload = self.receive(connection)
        self.assertEqual((kind, actual_id), (link.MESSAGE_ERROR, request_id))
        self.assertEqual(struct.unpack("!H", payload[:2])[0], code)
        payload[2:].decode("utf-8", "strict")
        self.assertLessEqual(len(payload), 1026)
        self.assert_closed(connection)

    def test_default_factory_is_native_and_http_is_explicit(self):
        self.assertIsInstance(self.server, link.LinkTCPServer)
        with self.assertRaises(ValueError):
            link.create_server("127.0.0.1", 0, self.root, transport="automatic")
        http = link.create_server("127.0.0.1", 0, self.root, transport="http")
        http.server_close()

    def test_complete_session_has_exact_resources_and_clean_goodbye(self):
        connection = self.hello()
        self.assertEqual(self.get(connection, "world.link"), (link.MESSAGE_RESOURCE, 1, self.manifest))
        self.assertEqual(self.get(connection, "scene.element", 2), (link.MESSAGE_RESOURCE, 2, b"scene {}\n"))
        connection.sendall(self.frame(link.MESSAGE_GOODBYE, 3))
        self.assert_closed(connection)

    def test_unicode_and_binary_resource_round_trip(self):
        connection = self.hello()
        expected = (self.world / "assets" / "연결.png").read_bytes()
        self.assertEqual(self.get(connection, "assets/연결.png"), (link.MESSAGE_RESOURCE, 1, expected))

    def test_frames_can_be_fragmented_byte_by_byte_or_coalesced(self):
        connection = self.connect()
        hello = b"\x00\x01hello-world"
        for byte in self.frame(link.MESSAGE_HELLO, payload=hello):
            connection.sendall(bytes([byte]))
        self.assertEqual(self.receive(connection), (link.MESSAGE_WELCOME, 0, hello))
        get = lambda i, path: self.frame(link.MESSAGE_GET, i, struct.pack("!I", link.IMAGE_LIMIT) + path)
        connection.sendall(get(1, b"world.link") + get(2, b"scene.element") + self.frame(link.MESSAGE_GOODBYE, 3))
        self.assertEqual(self.receive(connection), (link.MESSAGE_RESOURCE, 1, self.manifest))
        self.assertEqual(self.receive(connection), (link.MESSAGE_RESOURCE, 2, b"scene {}\n"))
        self.assert_closed(connection)

    def test_unknown_wire_version_is_bounded_error_without_reading_body(self):
        for major, minor in ((1, 0), (0, 2)):
            with self.subTest(version=(major, minor)):
                connection = self.connect()
                connection.sendall(self.frame(link.MESSAGE_HELLO, major=major, minor=minor, size=0xffffffff))
                self.assert_error(connection, link.ERROR_VERSION)

    def test_standard_version_and_world_slug_are_checked(self):
        for payload, code in ((b"\x00\x02hello-world", link.ERROR_VERSION),
                              (b"\x00\x01bad_world", link.ERROR_BAD_REQUEST),
                              (b"\x00\x01../hello-world", link.ERROR_BAD_REQUEST),
                              (b"\x00\x01\xff", link.ERROR_BAD_REQUEST)):
            with self.subTest(payload=payload):
                connection = self.connect()
                connection.sendall(self.frame(link.MESSAGE_HELLO, payload=payload))
                self.assert_error(connection, code)

    def test_first_message_and_control_bounds_fail_before_payload_allocation(self):
        cases = [
            self.frame(link.MESSAGE_GET),
            self.frame(link.MESSAGE_HELLO, 1),
            self.frame(link.MESSAGE_HELLO, flags=1),
            self.frame(255),
            self.frame(link.MESSAGE_HELLO, size=2),
            self.frame(link.MESSAGE_HELLO, size=2051),
            self.frame(link.MESSAGE_HELLO, size=0xffffffff),
        ]
        for frame in cases:
            with self.subTest(header=frame):
                connection = self.connect()
                connection.sendall(frame)
                self.assert_error(connection, link.ERROR_BAD_REQUEST, link.HEADER.unpack(frame[:16])[5])

    def test_http_and_other_magic_are_closed_without_fallback(self):
        for data in (b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n", self.frame(link.MESSAGE_HELLO, magic=b"NOPE")):
            connection = self.connect()
            connection.sendall(data)
            self.assert_closed(connection)

    def test_truncated_header_and_payload_close_session(self):
        for data in (b"LIN", self.frame(link.MESSAGE_HELLO, size=12) + b"\x00\x01h"):
            connection = self.connect()
            connection.sendall(data)
            connection.shutdown(socket.SHUT_WR)
            self.assert_closed(connection)

    def test_missing_world_or_manifest_is_not_found(self):
        for world in (b"missing", b"no-manifest"):
            (self.root / "no-manifest").mkdir(exist_ok=True)
            connection = self.connect()
            connection.sendall(self.frame(link.MESSAGE_HELLO, payload=b"\x00\x01" + world))
            self.assert_error(connection, link.ERROR_NOT_FOUND)

    def test_wrong_order_flags_types_ids_and_get_sizes_close_session(self):
        cases = [
            self.frame(link.MESSAGE_HELLO, 1),
            self.frame(link.MESSAGE_RESOURCE, 1),
            self.frame(link.MESSAGE_GET, 0),
            self.frame(link.MESSAGE_GET, 2),
            self.frame(link.MESSAGE_GET, 1, flags=1),
            self.frame(link.MESSAGE_GET, 1, size=4),
            self.frame(link.MESSAGE_GET, 1, size=2053),
            self.frame(link.MESSAGE_GET, 1, size=0xffffffff),
            self.frame(link.MESSAGE_GOODBYE, 1, b"x"),
        ]
        for frame in cases:
            connection = self.hello()
            connection.sendall(frame)
            self.assert_error(connection, link.ERROR_BAD_REQUEST, link.HEADER.unpack(frame[:16])[5])

    def test_repeat_request_id_is_rejected(self):
        connection = self.hello()
        self.get(connection, "world.link")
        self.get_error(connection, b"world.link", link.ERROR_BAD_REQUEST)

    def get_error(self, connection, path, code, maximum=link.IMAGE_LIMIT):
        connection.sendall(self.frame(link.MESSAGE_GET, 1, struct.pack("!I", maximum) + path))
        self.assert_error(connection, code, 1)

    def test_invalid_utf8_traversal_url_aliases_and_windows_aliases(self):
        invalid = [b"../world.link", b"/world.link", b"./world.link", b"assets//a.png", b"world.link/",
                   b"world.link?x=1", b"world.link#x", b"world.link%00", b"user@world.link", b"world.link\\x", b"world.link.",
                   b"world.link ", b"CON.element", b"assets/a:stream.png", b"assets/\x00.png", b"\xff"]
        for path in invalid:
            with self.subTest(path=path):
                self.get_error(self.hello(), path, link.ERROR_BAD_REQUEST)

    def test_client_and_resource_type_limits_are_both_enforced(self):
        self.get_error(self.hello(), b"world.link", link.ERROR_TOO_LARGE, len(self.manifest) - 1)
        (self.world / "large.script").write_bytes(b"x" * (link.SCRIPT_LIMIT + 1))
        self.get_error(self.hello(), b"large.script", link.ERROR_TOO_LARGE)
        (self.world / "large.script").write_bytes(b"x" * link.SCRIPT_LIMIT)
        result = self.get(self.hello(), "large.script", maximum=link.SCRIPT_LIMIT)
        self.assertEqual(len(result[2]), link.SCRIPT_LIMIT)
        for maximum in (0, link.IMAGE_LIMIT + 1, 0xffffffff):
            self.get_error(self.hello(), b"world.link", link.ERROR_BAD_REQUEST, maximum)

    def test_missing_resource_and_unpublished_type_are_not_found(self):
        (self.world / "secret.py").write_bytes(b"private")
        for path in (b"missing.png", b"secret.py", b"assets"):
            self.get_error(self.hello(), path, link.ERROR_NOT_FOUND)

    def test_world_is_fixed_and_cannot_cross_to_sibling(self):
        self.get_error(self.hello(), b"../second-world/world.link", link.ERROR_BAD_REQUEST)

    def test_session_request_limit_and_goodbye_at_boundary(self):
        connection = self.hello()
        for i in range(1, link.MAX_REQUESTS + 1):
            self.assertEqual(self.get(connection, "world.link", i)[0], link.MESSAGE_RESOURCE)
        connection.sendall(self.frame(link.MESSAGE_GET, link.MAX_REQUESTS + 1, struct.pack("!I", 1024) + b"world.link"))
        self.assert_error(connection, link.ERROR_LIMIT, link.MAX_REQUESTS + 1)
        # Closing at the exact maximum remains valid.
        connection = self.hello()
        for i in range(1, link.MAX_REQUESTS + 1):
            self.get(connection, "world.link", i)
        connection.sendall(self.frame(link.MESSAGE_GOODBYE, link.MAX_REQUESTS + 1))
        self.assert_closed(connection)

    def test_session_transfer_limit_is_enforced_on_actual_bytes(self):
        with (self.world / "large.png").open("wb") as stream:
            stream.truncate(link.IMAGE_LIMIT)
        (self.world / "extra.png").write_bytes(b"x")
        connection = self.hello()
        for i in range(1, 5):
            kind, request_id, body = self.get(connection, "large.png", i)
            self.assertEqual((kind, request_id, len(body)), (link.MESSAGE_RESOURCE, i, link.IMAGE_LIMIT))
            del body
        connection.sendall(self.frame(link.MESSAGE_GET, 5, struct.pack("!I", 1) + b"extra.png"))
        self.assert_error(connection, link.ERROR_LIMIT, 5)

    def directory_link(self, name, target):
        try:
            os.symlink(target, name, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                self.skipTest("Directory symlinks unavailable.")
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(name), str(target)],
                                    capture_output=True, timeout=5)
            if result.returncode:
                self.skipTest("Directory links unavailable.")

    def test_native_directory_link_cannot_escape_world(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        (outside / "secret.element").write_bytes(b"private")
        self.directory_link(self.world / "escape", outside)
        self.get_error(self.hello(), b"escape/secret.element", link.ERROR_FORBIDDEN)

    def test_native_world_entry_cannot_alias_outside_root(self):
        outside = Path(self.temporary.name) / "private-world"
        outside.mkdir()
        (outside / "world.link").write_bytes(b"private")
        self.directory_link(self.root / "alias-world", outside)
        connection = self.connect()
        connection.sendall(self.frame(link.MESSAGE_HELLO, payload=b"\x00\x01alias-world"))
        self.assert_error(connection, link.ERROR_FORBIDDEN)
    def test_reads_are_fresh_per_get_without_snapshot_claim(self):
        connection = self.hello()
        self.get(connection, "world.link")
        changed = b"scene { changed }\n"
        (self.world / "scene.element").write_bytes(changed)
        self.assertEqual(self.get(connection, "scene.element", 2)[2], changed)

    def test_partial_message_cannot_extend_deadline_with_slow_bytes(self):
        with mock.patch.object(link, "REQUEST_TIMEOUT", .20):
            connection = self.connect()
            data = self.frame(link.MESSAGE_HELLO, payload=b"\x00\x01hello-world")
            connection.sendall(data[:8])
            time.sleep(.12)
            connection.sendall(data[8:16])
            time.sleep(.13)
            self.assert_closed(connection)

    def test_idle_session_times_out(self):
        with mock.patch.object(link, "REQUEST_TIMEOUT", .10):
            connection = self.hello()
            time.sleep(.18)
            self.assert_closed(connection)

    def test_parallel_clients_have_independent_request_ids(self):
        def fetch(_):
            with socket.create_connection(("127.0.0.1", self.port), timeout=2) as connection:
                self.hello(connection)
                result = self.get(connection, "world.link")
                connection.sendall(self.frame(link.MESSAGE_GOODBYE, 2))
                return result
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(fetch, range(24)))
        self.assertTrue(all(item == (link.MESSAGE_RESOURCE, 1, self.manifest) for item in results))

    def test_connection_admission_is_bounded_before_threads(self):
        occupied = [self.hello() for _ in range(link.MAX_CLIENTS)]
        self.assert_error(self.connect(), link.ERROR_BUSY)
        # Existing sessions remain usable even when admission rejects a new peer.
        self.assertEqual(self.get(occupied[0], "world.link")[2], self.manifest)
    def test_server_close_disconnects_idle_clients(self):
        connection = self.hello()
        self.server.shutdown()
        self.server.server_close()
        self.assert_closed(connection)


if __name__ == "__main__":
    unittest.main()