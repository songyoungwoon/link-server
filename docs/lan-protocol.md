# Legacy LINK LAN HTTP v0.1

The default server now uses [LINK Protocol 0.1 over TCP](link-protocol-v0.1.md). This document describes only the explicit `--transport http` compatibility mode for older LINK Browser builds.

The legacy address, resource, portal and loading contract remains documented in the browser repository:

[Legacy LINK LAN HTTP v0.1](https://github.com/songyoungwoon/link/blob/4321e98/docs/link-lan-v0.1.md)

- `link://<IPv4>[:port]/<world>` maps to HTTP `/<world>/world.link` in that older browser. Default port: 8000.
- The server supports read-only GET/HEAD, an index page and optional `/.well-known/link` metadata.
- Resource path confinement and per-file size limits still apply. HTTP requests are independent; the server does not track a navigation's total byte count in this mode.
- The transport is plain HTTP without TLS, authentication or shared multiplayer state.
- A native LINK/TCP browser cannot connect to this mode. There is no automatic transport fallback.

Run legacy HTTP on a separate port when comparing old and new browsers:

~~~powershell
python .\link_server.py --transport http --port 8001
~~~