"""Tiny UDP transport so the teleop app can stream joint states to a separate viewer process.

UDP on loopback is ideal here: fire-and-forget, never blocks the control loop, and if the viewer
isn't running the packets are simply dropped.
"""

from __future__ import annotations

import json
import socket


class JointStatePublisher:
    """Sends a ``{motor: normalized_value}`` dict as a JSON UDP datagram."""

    def __init__(self, host: str = "127.0.0.1", port: int = 50607):
        self._addr = (host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def publish(self, positions: dict[str, float]) -> None:
        try:
            self._sock.sendto(json.dumps(positions).encode("utf-8"), self._addr)
        except OSError:
            pass  # viewer not up / transient error -> drop

    def close(self) -> None:
        self._sock.close()


def make_receiver(host: str = "127.0.0.1", port: int = 50607) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    sock.bind((host, port))
    return sock


def drain_latest(sock: socket.socket) -> dict[str, float] | None:
    """Discard backlog and return only the most recent joint-state packet (or None)."""
    latest = None
    while True:
        try:
            data, _ = sock.recvfrom(65535)
            latest = data
        except (BlockingIOError, OSError):
            break
    if latest is None:
        return None
    try:
        return json.loads(latest.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
