# LINK Protocol 0.1 — native TCP

The canonical wire contract is maintained with LINK Browser:

[LINK Protocol 0.1](https://github.com/songyoungwoon/link/blob/main/docs/link-protocol-v0.1.md)

In sibling checkouts, the same source is `../link/docs/link-protocol-v0.1.md`. Update browser and server together when changing the contract.

This reference implementation uses one plain TCP connection per world load:

- The browser connects to the IPv4 and port in `link://<IPv4>[:port]/<world>`. The default port is 8000.
- Every message has a 16-byte header in network byte order: `!4sBBBBII` = magic `LINK`, protocol major 0, minor 1, type, zero flags, request ID, payload byte length.
- The first message is HELLO (type 1), ID 0, with bytes `00 01` for World Standards 0.1 followed by an ASCII world slug. WELCOME (type 2) echoes that payload after checking the published world and manifest.
- GET (type 3) IDs increase from 1. Its payload is a uint32 maximum resource size followed by an already-decoded relative UTF-8 path. RESOURCE (type 4) returns the exact file bytes with the same ID.
- ERROR (type 5) contains a uint16 code followed by at most 1,024 UTF-8 message bytes. Codes are BAD_REQUEST 1, NOT_FOUND 2, FORBIDDEN 3, TOO_LARGE 4, VERSION 5, BUSY 6, INTERNAL 7 and LIMIT 8. An error terminates the session. A server at its client limit may send BUSY with ID 0 before HELLO.
- GOODBYE (type 6) uses the next ID, has an empty payload and closes without a response. Truncated frames or invalid magic close without a response. HTTP is never auto-detected or used as a fallback.
- A session is limited to 256 GETs and 64 MiB of successfully returned resource bytes, with at most 32 concurrent sessions. Resource type limits and the client-supplied cap both apply.
- A control payload is bounded before reading: HELLO 3–2,050 bytes, GET 5–2,052 bytes, GOODBYE zero bytes. A 10-second absolute receive deadline covers the complete header and body of each message. Socket writes have a 10-second timeout.
- Relative portal addresses retain the server authority. Portal navigation and refresh create a new session.
- Reads are fresh per GET. The server does not promise an immutable world snapshot while its files are being edited.

This profile does not provide TLS, peer authentication, access control, a multiplayer service or live scene streaming. It is an experimental application protocol over TCP, not a new IP transport. Preserve a trusted network boundary while testing.

The old HTTP file provider is available only through `--transport http`. See the [legacy contract](lan-protocol.md) and [server README](../README.md).