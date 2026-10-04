"""
protocol.py - Application-level protocol for the P2P network.

TCP is a byte stream, so we need our own message boundaries (framing).
Every control message is sent as:

    [4-byte length (big-endian)][JSON payload (UTF-8)]

File transfer is two stages on the same connection:

    1. a framed JSON "file" message (metadata: filename, filesize)
    2. exactly `filesize` raw bytes of the file (no framing)
"""

import json
import struct

HEADER_SIZE = 4                  # 4-byte unsigned int holds the JSON length
MAX_MESSAGE_SIZE = 1024 * 1024   # reject absurd JSON sizes (1 MB)
CHUNK_SIZE = 64 * 1024           # files are sent/received in 64 KB chunks

# Message types
HELLO = "hello"
HELLO_ACK = "hello_ack"
TEXT = "text"
FILE = "file"


class ProtocolError(Exception):
    """Raised when the other side sends something that breaks the protocol."""


# ---------------------------------------------------------------- framing
def encode_message(message: dict) -> bytes:
    """dict -> [4-byte length][JSON bytes]"""
    payload = json.dumps(message).encode("utf-8")
    return struct.pack("!I", len(payload)) + payload


def recv_exact(sock, size: int) -> bytes:
    """
    Read EXACTLY `size` bytes from the socket.

    A single recv() may return fewer bytes than requested (TCP has no
    message boundaries), so we loop until everything has arrived.
    """
    buffer = bytearray()
    while len(buffer) < size:
        chunk = sock.recv(size - len(buffer))
        if not chunk:  # empty bytes => the other side closed the connection
            raise ConnectionError("connection closed by peer")
        buffer.extend(chunk)
    return bytes(buffer)


def send_message(sock, message: dict) -> None:
    sock.sendall(encode_message(message))


def recv_message(sock) -> dict:
    """Read one framed JSON message."""
    header = recv_exact(sock, HEADER_SIZE)
    (length,) = struct.unpack("!I", header)
    if length == 0 or length > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"invalid message length: {length}")
    payload = recv_exact(sock, length)
    try:
        message = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"malformed message: {exc}") from exc
    if not isinstance(message, dict) or "type" not in message:
        raise ProtocolError("message must be a JSON object with a 'type'")
    return message


# ------------------------------------------------------- message builders
def make_hello(msg_type: str, peer_id: str, peer_name: str, port: int) -> dict:
    """Used for both HELLO and HELLO_ACK (they carry the same fields)."""
    return {"type": msg_type, "peer_id": peer_id,
            "peer_name": peer_name, "port": port}


def make_text(sender_id: str, sender_name: str, message: str) -> dict:
    return {"type": TEXT, "sender_id": sender_id,
            "sender_name": sender_name, "message": message}


def make_file(sender_id: str, sender_name: str,
              filename: str, filesize: int) -> dict:
    return {"type": FILE, "sender_id": sender_id, "sender_name": sender_name,
            "filename": filename, "filesize": filesize}
