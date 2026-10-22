# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""Real network tests; no third-party packages, fixed ports or firewall changes."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import contextlib
import http.client
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import link_server


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="link-lan-test-")
        self.base = Path(self.temporary.name)
        self.root = self.base / "worlds"
        self.world = self.root / "hello-world"
        self.world.mkdir(parents=True)
        self.manifest = b'world { version: "0.1"; id: "hello-world"; }\n'
        (self.world / "world.link").write_bytes(self.manifest)
        (self.world / "scene.element").write_bytes(b"scene {}\n")
        (self.world / "appearance.style").write_bytes(b"defaults {}\n")
        (self.world / "scripts").mkdir()
        (self.world / "scripts" / "remote.script").write_bytes(b"on onStart(ctx) {}\n")
        self.server = link_server.create_server("127.0.0.1", 0, self.root, transport="http")
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, target, method="GET", body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.request(method, target, body=body)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def assert_response(self, target, status, method="GET"):
        actual, headers, body = self.request(target, method)
        self.assertEqual(actual, status, (target, body))
        if method == "HEAD":
            self.assertEqual(body, b"")
        else:
            self.assertEqual(int(headers["Content-Length"]), len(body))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Connection"], "close")
        return headers, body

    def test_manifest_get_and_head_have_exact_byte_lengths(self):
        headers, body = self.assert_response("/hello-world/world.link", 200)
        self.assertEqual(body, self.manifest)
        self.assertEqual(headers["Content-Type"], "text/plain; charset=utf-8")
        head, _ = self.assert_response("/hello-world/world.link", 200, "HEAD")
        self.assertEqual(head["Content-Length"], headers["Content-Length"])
        self.assertEqual(head["Content-Type"], headers["Content-Type"])

    def test_relative_documents_are_transferred_unchanged(self):
        for filename in ("scene.element", "appearance.style", "scripts/remote.script"):
            with self.subTest(filename=filename):
                _, body = self.assert_response("/hello-world/" + filename, 200)
                self.assertEqual(body, (self.world / filename).read_bytes())

    def test_unicode_resource_and_content_are_utf8(self):
        filename = "자료/연결.element"
        path = self.world / filename
        path.parent.mkdir()
        expected = "scene {} // 한글 UTF-8\n".encode("utf-8")
        path.write_bytes(expected)
        _, body = self.assert_response("/hello-world/" + quote(filename), 200)
        self.assertEqual(body, expected)

    def test_png_mime_and_binary_body(self):
        expected = (link_server.DEFAULT_WORLDS / "hello-world" / "assets" / "연결.png").read_bytes()
        (self.world / "image.png").write_bytes(expected)
        headers, body = self.assert_response("/hello-world/image.png", 200)
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertEqual(body, expected)
        self.assertTrue(body.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_index_and_metadata_do_not_list_the_filesystem(self):
        _, index = self.assert_response("/", 200)
        self.assertIn(b"LINK LAN Server", index)
        self.assertNotIn(str(self.root).encode(), index)
        headers, body = self.assert_response("/.well-known/link", 200)
        metadata = json.loads(body)
        self.assertEqual(metadata["protocol"], "LINK")
        self.assertEqual(metadata["manifest_template"], "/{world}/world.link")
        self.assertFalse(metadata["shared_multiplayer_state"])
        self.assertEqual(metadata["limits"]["image_bytes"], 16 * 1024 * 1024)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertNotIn(str(self.root).encode(), body)

    def test_missing_paths_and_directories_do_not_redirect_or_list(self):
        for target in ("/missing/world.link", "/hello-world/missing.element", "/hello-world", "/hello-world/scripts", "/README.md", "/.git/config"):
            with self.subTest(target=target):
                headers, _ = self.assert_response(target, 404)
                self.assertNotIn("Location", headers)
        self.assert_response("/hello-world/missing.element", 404, "HEAD")

    def test_only_read_methods_are_supported(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT", "CUSTOM"):
            with self.subTest(method=method):
                headers, _ = self.assert_response("/hello-world/world.link", 405, method)
                self.assertEqual(headers["Allow"], "GET, HEAD")
        self.assertEqual((self.world / "world.link").read_bytes(), self.manifest)

    def test_traversal_encoded_separators_and_nested_escapes_are_rejected(self):
        targets = [
            "/hello-world/../world.link", "/hello-world/%2e%2e/world.link",
            "/hello-world/%2E/world.link", "/hello-world/%2fworld.link",
            "/hello-world/%5Cworld.link", "/hello-world/%252e%252e/world.link",
            "/hello-world/%252Fworld.link", "/hello-world/scene.element?x=1",
            "/hello-world/scene.element%3Fx=1", "/hello-world/world.link#fragment",
            "/hello-world/%", "/hello-world/%GG.element", "/hello-world/%ff.element",
            "/hello-world/%c0%afworld.link", "/hello-world/%00.element",
            "/hello-world/a:stream.element", "/hello-world/CON.element",
            "/hello-world/scene.element.", "/hello-world/scene.element%20",
            "/hello-world//scene.element", "//hello-world/world.link",
            "/hello-world\\world.link", "/hello-world/",
            "http://127.0.0.1/hello-world/world.link",
        ]
        for target in targets:
            with self.subTest(target=target):
                self.assert_response(target, 400)

    def test_world_slug_is_ascii_letters_digits_hyphen(self):
        for slug in ("bad_world", "bad.world", quote("한글")):
            (self.root / ("한글" if "%" in slug else slug)).mkdir()
            self.assert_response("/" + slug + "/world.link", 404)
        valid = self.root / "Mixed-Case-123"
        valid.mkdir()
        (valid / "world.link").write_bytes(self.manifest)
        self.assert_response("/Mixed-Case-123/world.link", 200)

    def test_non_world_resource_types_are_not_published(self):
        for filename in ("secret.txt", "inventory.json", "program.py", "page.html", "other.link"):
            (self.world / filename).write_text("private", encoding="utf-8")
            self.assert_response("/hello-world/" + filename, 404)

    def test_all_document_and_image_size_caps(self):
        cases = (("world.link", 64 * 1024), ("big.element", 1024 * 1024), ("big.style", 1024 * 1024), ("big.script", 128 * 1024), ("big.png", 16 * 1024 * 1024))
        for filename, limit in cases:
            with self.subTest(filename=filename):
                with (self.world / filename).open("wb") as stream:
                    stream.truncate(limit + 1)
                self.assert_response("/hello-world/" + filename, 413)
                self.assert_response("/hello-world/" + filename, 413, "HEAD")

    def test_exact_limit_is_accepted(self):
        content = b"x" * (128 * 1024)
        (self.world / "exact.script").write_bytes(content)
        _, body = self.assert_response("/hello-world/exact.script", 200)
        self.assertEqual(body, content)

    def make_directory_link(self, link, target):
        try:
            os.symlink(target, link, target_is_directory=True)
            return
        except OSError:
            if os.name != "nt":
                self.skipTest("Directory symlinks unavailable on this filesystem.")
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, timeout=5)
        if result.returncode:
            self.skipTest("Neither directory symlinks nor Windows junctions are available.")

    def test_directory_link_cannot_escape_world_to_sibling_or_outside_root(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "secret.element").write_bytes(b"outside root")
        sibling = self.root / "second-world"
        sibling.mkdir()
        (sibling / "secret.element").write_bytes(b"other world")
        for name, target in (("outside-link", outside), ("sibling-link", sibling)):
            with self.subTest(name=name):
                self.make_directory_link(self.world / name, target)
                self.assert_response("/hello-world/" + name + "/secret.element", 403)

    def test_world_entry_cannot_be_a_directory_link(self):
        outside = self.base / "outside-world"
        outside.mkdir()
        (outside / "world.link").write_bytes(b"private world")
        self.make_directory_link(self.root / "alias-world", outside)
        self.assert_response("/alias-world/world.link", 403)

    def test_file_symlink_cannot_escape_world(self):
        outside = self.base / "outside.element"
        outside.write_bytes(b"outside secret")
        try:
            os.symlink(outside, self.world / "escape.element")
        except OSError:
            self.skipTest("File symlinks require Windows Developer Mode or symbolic-link privilege.")
        self.assert_response("/hello-world/escape.element", 403)

    def test_multiple_clients_can_fetch_in_parallel(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            responses = list(executor.map(lambda _: self.request("/hello-world/world.link"), range(24)))
        self.assertTrue(all(status == 200 and body == self.manifest for status, _, body in responses))

    def test_configured_root_is_independent_of_current_working_directory(self):
        previous = Path.cwd()
        try:
            os.chdir(self.base)
            self.assert_response("/hello-world/world.link", 200)
            default_server = link_server.create_server("127.0.0.1", 0, transport="http")
            try:
                self.assertEqual(default_server.worlds_root, Path(link_server.__file__).resolve().parent / "worlds")
                resolved, world, limit, _ = link_server.resolve_resource(default_server.worlds_root, "/hello-world/world.link")
                self.assertIn(b'"hello-world"', link_server.read_resource(resolved, world, limit))
            finally:
                default_server.server_close()
        finally:
            os.chdir(previous)

    def test_startup_advertises_every_host_ipv4_and_actual_port(self):
        server = link_server.create_server("0.0.0.0", 0, self.root, transport="http")
        try:
            output = io.StringIO()
            with mock.patch.object(link_server, "lan_ipv4_addresses", return_value=["198.51.100.42", "192.168.128.1"]):
                with contextlib.redirect_stdout(output):
                    link_server.print_startup(server)
            text = output.getvalue()
            port = server.server_address[1]
            for address in ("198.51.100.42", "192.168.128.1", "127.0.0.1"):
                self.assertIn(f"link://{address}:{port}/hello-world", text)
            self.assertNotIn("link://0.0.0.0", text)
        finally:
            server.server_close()


if __name__ == "__main__":
    unittest.main()