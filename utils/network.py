"""Network / internet connectivity helpers."""

from __future__ import annotations

import socket

# Standard Persian message as requested by user
NO_INTERNET_MSG = "اینترنت کانکشن نداری"
NO_INTERNET_DETAIL = "اینترنت کانکشن نداری! لطفاً اتصال اینترنت خود را بررسی کن."

# Keywords that typically indicate a network / DNS failure in git stderr
_NETWORK_ERROR_KEYWORDS = (
    "could not resolve host",
    "could not resolve hostname",
    "unable to access",
    "failed to connect",
    "connection timed out",
    "network is unreachable",
    "no internet",
    "temporary failure in name resolution",
    "name or service not known",
    "getaddrinfo",
    "connection refused",
    "timed out",
    "dial tcp",
    "proxy",
)


def has_internet_connection(timeout: float = 3.0) -> bool:
    """Return True if internet appears reachable.

    Tries a TCP connection to well-known public DNS servers first
    (no DNS required), then falls back to a DNS-based host.
    Uses stdlib only, no external dependencies.
    """
    # 1) Direct IP reachability (does not need DNS)
    for host, port in (("8.8.8.8", 53), ("1.1.1.1", 53), ("8.8.8.8", 80), ("1.1.1.1", 80)):
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True
        except OSError:
            continue

    # 2) DNS-based check as final fallback
    for host, port in (("www.google.com", 80), ("www.cloudflare.com", 80)):
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True
        except OSError:
            continue

    return False


def is_network_error_message(message: str) -> bool:
    """Heuristic: does the git stderr look like a network failure?"""
    lower = message.lower()
    return any(kw in lower for kw in _NETWORK_ERROR_KEYWORDS)


def ensure_internet_or_raise(timeout: float = 3.0) -> None:
    """Raise GitManagerError with Persian message if offline."""
    # Local import to avoid circular dependency at module load time
    from core.git_operations import GitManagerError  # noqa: WPS433

    if not has_internet_connection(timeout=timeout):
        raise GitManagerError(f"{NO_INTERNET_MSG} — {NO_INTERNET_DETAIL}")
