# LINK Protocol — LAN HTTP v0.1

The canonical address, resource, portal, loading, timeout and compatibility contract is maintained with LINK Browser:

[LINK Protocol — LAN HTTP v0.1](https://github.com/songyoungwoon/link/blob/main/docs/link-lan-v0.1.md)

When working in sibling checkouts, the same source document is `../link/docs/link-lan-v0.1.md` from the server repository root. Keep browser and server updates together when changing this contract; the document above becomes available on GitHub when the matching browser changes are pushed.

This server is a reference file provider for that contract:

- `link://<IPv4>[:port]/<world>` maps to HTTP `/<world>/world.link`; the default port is 8000.
- Manifest documents, Element, Script, Style and images remain relative to their world directory.
- `/second-world` portals retain the server IP and port; explicit `link://local/...` means the visiting browser's local worlds.
- The server supports GET/HEAD and optional `/.well-known/link` metadata. Scripts execute in the browser. Shared multiplayer state is not implemented.
- The initial transport uses plain HTTP on a trusted LAN. Domain names, HTTPS and authentication remain future work.

See the [server README](../README.md) for Windows startup, IP selection, root configuration, tests and a manual LAN-only firewall rule.