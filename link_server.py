#!/usr/bin/env python3
# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""Read-only LINK World Standards v0.1 HTTP transport for a trusted LAN.

Python 3.10+, standard library only. Run this file from any working directory.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote_to_bytes

DEFAULT_WORLDS = Path(__file__).resolve().parent / "worlds"
MANIFEST_LIMIT = 64 * 1024
DOCUMENT_LIMIT = 1024 * 1024
SCRIPT_LIMIT = 128 * 1024
IMAGE_LIMIT = 16 * 1024 * 1024
WORLD_TRANSFER_LIMIT = 64 * 1024 * 1024  # Enforced across a navigation by the browser.
REQUEST_TIMEOUT = 10
WORLD_SLUG = re.compile(r"[A-Za-z0-9-]+\Z", re.ASCII)
BAD_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
ENCODED_SEPARATOR = re.compile(r"%(?:2f|5c)", re.IGNORECASE)
RESERVED_NAME = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z", re.IGNORECASE)
RESOURCE_TYPES = {
    ".element": (DOCUMENT_LIMIT, "text/plain; charset=utf-8"),
    ".style": (DOCUMENT_LIMIT, "text/plain; charset=utf-8"),
    ".script": (SCRIPT_LIMIT, "text/plain; charset=utf-8"),
    ".png": (IMAGE_LIMIT, "image/png"),
    ".jpg": (IMAGE_LIMIT, "image/jpeg"),
    ".jpeg": (IMAGE_LIMIT, "image/jpeg"),
    ".bmp": (IMAGE_LIMIT, "image/bmp"),
    ".gif": (IMAGE_LIMIT, "image/gif"),
    ".webp": (IMAGE_LIMIT, "image/webp"),
    ".tif": (IMAGE_LIMIT, "image/tiff"),
    ".tiff": (IMAGE_LIMIT, "image/tiff"),
    ".ico": (IMAGE_LIMIT, "image/x-icon"),
}
INDEX = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>LINK LAN Server</title><body><h1>LINK LAN Server</h1>
<p>Read-only world documents for LINK Browser. This page does not render a world.</p>
<p>Enter <code>link://SERVER-IPv4:8000/hello-world</code> in a LINK Browser
that supports LAN HTTP transport. Use the address printed in the server terminal.</p>
<p><a href="/.well-known/link">Transport metadata</a></p>
<p>Trusted LAN HTTP only. No authentication or shared multiplayer state.</p></body></html>
""".encode("utf-8")
METADATA = json.dumps({
    "protocol": "LINK",
    "profile": "lan-http",
    "version": "0.1",
    "world_standards": "0.1",
    "transport": "http",
    "manifest_template": "/{world}/world.link",
    "default_world": "hello-world",
    "shared_multiplayer_state": False,
    "limits": {
        "manifest_bytes": MANIFEST_LIMIT,
        "element_bytes": DOCUMENT_LIMIT,
        "style_bytes": DOCUMENT_LIMIT,
        "script_bytes": SCRIPT_LIMIT,
        "image_bytes": IMAGE_LIMIT,
        "world_transfer_bytes": WORLD_TRANSFER_LIMIT,
    },
}, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


class RequestError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def decode_target(raw: str) -> str:
    """Decode exactly once and reject ambiguous URL and Windows path spellings."""
    if not raw.startswith("/") or raw.startswith("//"):
        raise RequestError(400, "Use an origin-form absolute path.")
    if any(char in raw for char in "\\?#") or BAD_ESCAPE.search(raw) or ENCODED_SEPARATOR.search(raw):
        raise RequestError(400, "Invalid or ambiguous URL path.")
    try:
        raw.encode("ascii", "strict")
        path = unquote_to_bytes(raw).decode("utf-8", "strict")
    except (UnicodeError, ValueError):
        raise RequestError(400, "Paths must use valid percent-encoded UTF-8.") from None
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise RequestError(400, "Control characters are not allowed in paths.")
    if any(char in path for char in "%\\?#<>:\"|*"):
        raise RequestError(400, "Invalid or nested-encoded path.")
    if path != "/":
        for part in path[1:].split("/"):
            if not part or part in (".", "..") or part.endswith((".", " ")) or RESERVED_NAME.fullmatch(part):
                raise RequestError(400, "Invalid path segment.")
    return path


def resource_type(path: Path) -> tuple[int, str]:
    if path.name == "world.link":
        return MANIFEST_LIMIT, "text/plain; charset=utf-8"
    result = RESOURCE_TYPES.get(path.suffix.lower())
    if result is None:
        raise RequestError(404, "This resource type is not published.")
    return result


def resolve_resource(root: Path, path: str) -> tuple[Path, Path, int, str]:
    parts = path[1:].split("/")
    if len(parts) < 2 or not WORLD_SLUG.fullmatch(parts[0]):
        raise RequestError(404, "World resource not found.")
    world_lexical = root / parts[0]
    try:
        world = world_lexical.resolve(strict=True)
        # A world entry may not alias another world or a directory outside the root.
        if world != world_lexical or not world.is_relative_to(root):
            raise RequestError(403, "World directory escapes its published location.")
        if not world.is_dir():
            raise RequestError(404, "World not found.")
        requested = world.joinpath(*parts[1:])
        limit, mime = resource_type(requested)
        resolved = requested.resolve(strict=True)
        if not resolved.is_relative_to(world):
            raise RequestError(403, "Resource escapes its world directory.")
        real_limit, _ = resource_type(resolved)
        if not stat.S_ISREG(resolved.stat().st_mode):
            raise RequestError(404, "Resource is not a regular file.")
        return resolved, world, min(limit, real_limit), mime
    except FileNotFoundError:
        raise RequestError(404, "Resource not found.") from None
    except (PermissionError, RuntimeError):
        raise RequestError(403, "Resource is not accessible.") from None
    except OSError:
        raise RequestError(404, "Resource not found.") from None


def read_resource(path: Path, world: Path, limit: int) -> bytes:
    try:
        if path.stat().st_size > limit:
            raise RequestError(413, f"Resource exceeds its {limit}-byte limit.")
        if not path.resolve(strict=True).is_relative_to(world):
            raise RequestError(403, "Resource escapes its world directory.")
        with path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise RequestError(404, "Resource is not a regular file.")
            if info.st_size > limit:
                raise RequestError(413, f"Resource exceeds its {limit}-byte limit.")
            # Never send partial oversized content, including files changed during a read.
            body = stream.read(limit + 1)
        if len(body) > limit:
            raise RequestError(413, f"Resource exceeds its {limit}-byte limit.")
        return body
    except FileNotFoundError:
        raise RequestError(404, "Resource not found.") from None
    except (PermissionError, RuntimeError):
        raise RequestError(403, "Resource is not accessible.") from None
    except OSError:
        raise RequestError(404, "Resource not found.") from None


class LinkHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 32

    def __init__(self, address: tuple[str, int], worlds_root: Path):
        self.worlds_root = worlds_root
        super().__init__(address, LinkRequestHandler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(REQUEST_TIMEOUT)
        return connection, address


class LinkRequestHandler(BaseHTTPRequestHandler):
    server_version = "LINK-LAN/0.1"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def version_string(self) -> str:
        return self.server_version

    def do_GET(self) -> None:
        self._serve(head_only=False)

    def do_HEAD(self) -> None:
        self._serve(head_only=True)

    def __getattr__(self, name):
        if name.startswith("do_"):
            return self._unsupported_method
        raise AttributeError(name)

    def _unsupported_method(self) -> None:
        self._respond(405, b"Only GET and HEAD are supported.\n", "text/plain; charset=utf-8", allow=True)

    def handle_expect_100(self) -> bool:
        self._unsupported_method()
        return False

    def _serve(self, head_only: bool) -> None:
        try:
            # BaseHTTPRequestHandler normalizes leading //; inspect the original target.
            raw = self.raw_requestline.decode("iso-8859-1").split()[1]
            path = decode_target(raw)
            if path == "/":
                self._respond(200, INDEX, "text/html; charset=utf-8", head_only)
            elif path == "/.well-known/link":
                self._respond(200, METADATA, "application/json; charset=utf-8", head_only)
            else:
                resolved, world, limit, mime = resolve_resource(self.server.worlds_root, path)
                self._respond(200, read_resource(resolved, world, limit), mime, head_only)
        except RequestError as error:
            self._respond(error.status, (error.message + "\n").encode("utf-8"), "text/plain; charset=utf-8", head_only)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True

    def _respond(self, status: int, body: bytes, content_type: str, head_only: bool = False, allow: bool = False) -> None:
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        if content_type.startswith("text/html"):
            self.send_header("Content-Security-Policy", "default-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if allow:
            self.send_header("Allow", "GET, HEAD")
        self.end_headers()
        if not head_only and self.command != "HEAD":
            self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        message = format % args
        # Keep terminal logs readable and prevent request-line control characters.
        message = "".join(char if 32 <= ord(char) != 127 else f"\\x{ord(char):02x}" for char in message)
        print(f"[{self.log_date_time_string()}] {self.client_address[0]} {message}", flush=True)


def create_server(host: str = "0.0.0.0", port: int = 8000, worlds_root: Path | str | None = None) -> LinkHTTPServer:
    ipaddress.IPv4Address(host)
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535.")
    root = Path(worlds_root if worlds_root is not None else DEFAULT_WORLDS).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Worlds root must be an existing directory.")
    return LinkHTTPServer((host, port), root)


def lan_ipv4_addresses() -> list[str]:
    candidates = set()
    try:
        candidates.update(info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
    except OSError:
        pass
    # UDP connect asks the OS for its preferred local interface; no packets are sent.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            candidates.add(probe.getsockname()[0])
    except OSError:
        pass
    return sorted(address for address in candidates if not (
        ipaddress.IPv4Address(address).is_loopback
        or ipaddress.IPv4Address(address).is_unspecified
        or ipaddress.IPv4Address(address).is_multicast
    ))


def print_startup(server: LinkHTTPServer) -> None:
    host, port = server.server_address
    print(f"LINK LAN Server v0.1 | HTTP {host}:{port}", flush=True)
    print(f"Worlds root: {server.worlds_root}", flush=True)
    if host == "0.0.0.0":
        addresses = lan_ipv4_addresses()
        for address in addresses:
            print(f"  LAN:   link://{address}:{port}/hello-world", flush=True)
        if not addresses:
            print("  LAN IPv4 not detected. Use ipconfig to find this computer's IPv4 address.", flush=True)
        print(f"  Local: link://127.0.0.1:{port}/hello-world", flush=True)
    else:
        print(f"  LINK:  link://{host}:{port}/hello-world", flush=True)
    print("Trusted LAN HTTP only; GET/HEAD; no shared multiplayer state. Ctrl+C to stop.", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0", help="IPv4 address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", default=8000, type=int, help="TCP port (default: 8000)")
    parser.add_argument("--worlds", default=str(DEFAULT_WORLDS), type=Path, help="Published worlds root (default: script-relative worlds)")
    args = parser.parse_args(argv)
    try:
        server = create_server(args.host, args.port, args.worlds)
    except (OSError, ValueError) as error:
        parser.error(f"Cannot start LINK LAN server: {error}")
    try:
        print_startup(server)
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nLINK LAN Server stopped.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        raise SystemExit("LINK LAN Server requires Python 3.10 or newer.")
    raise SystemExit(main())