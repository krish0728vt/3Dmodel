"""Port availability checks.

This module never terminates anything. A busy port is reported so the caller can
choose another one or stop the owning process deliberately -- killing whatever
happens to hold a port is not a behavior this launcher offers.
"""

from __future__ import annotations

import socket


class PortUnavailableError(RuntimeError):
    """Raised when a required port is occupied and no alternative was requested."""

    def __init__(self, port: int, flag: str) -> None:
        self.port = port
        self.flag = flag
        super().__init__(
            f"Port {port} is already in use.\n"
            f"  Use {flag} <other-port> to pick a different port,\n"
            f"  or stop the process using port {port} yourself.\n"
            f"  SHAH never terminates a process just because it holds a port."
        )


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """True when a TCP listener can bind `host:port` right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # Deliberately no SO_REUSEADDR: we want to know whether a real server is
        # bound, which is exactly what an unadorned bind() tells us on Windows.
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def find_available_port(
    start_port: int,
    host: str = "127.0.0.1",
    *,
    attempts: int = 20,
) -> int | None:
    """First free port at or after `start_port`, or None if none found."""
    for offset in range(attempts):
        candidate = start_port + offset
        if candidate > 65535:
            return None
        if is_port_available(candidate, host):
            return candidate
    return None


def resolve_port(
    port: int,
    *,
    host: str = "127.0.0.1",
    flag: str,
    auto: bool = False,
) -> int:
    """Validate `port`, or pick the next free one when `auto` is set.

    Raises PortUnavailableError with an actionable message when the port is busy
    and `auto` is False.
    """
    if is_port_available(port, host):
        return port
    if not auto:
        raise PortUnavailableError(port, flag)
    alternative = find_available_port(port + 1, host)
    if alternative is None:
        raise PortUnavailableError(port, flag)
    return alternative
