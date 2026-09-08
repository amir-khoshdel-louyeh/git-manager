"""Network / internet connectivity helpers."""

from __future__ import annotations

import socket

NO_INTERNET_MSG = "No internet connection"
NO_INTERNET_DETAIL = "No internet connection! Please check your internet connection."

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


_internet_cache: dict[str, float | bool] = {"result": False, "time": 0.0}
_CACHE_TTL = 5.0  # seconds


def has_internet_connection(timeout: float = 1.0) -> bool:
    """Return True if internet appears reachable.

    Tries a TCP connection to well-known public DNS servers first
    (no DNS required), then falls back to a DNS-based host.
    Uses stdlib only, no external dependencies.
    Cached for a few seconds to avoid repeated blocking.
    """
    import time

    now = time.monotonic()
    # Use cache for fast repeated checks (e.g., opening dialogs)
    try:
        if now - float(_internet_cache.get("time", 0)) < _CACHE_TTL:
            return bool(_internet_cache.get("result"))
    except Exception:
        pass

    # Fast path: try single primary host with short timeout
    for host, port in (("8.8.8.8", 53), ("1.1.1.1", 53)):
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            _internet_cache["result"] = True
            _internet_cache["time"] = now
            return True
        except OSError:
            continue

    # Fallback: try DNS host with slightly longer timeout but still short
    for host, port in (("8.8.8.8", 80), ("www.google.com", 80)):
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            _internet_cache["result"] = True
            _internet_cache["time"] = now
            return True
        except OSError:
            continue

    _internet_cache["result"] = False
    _internet_cache["time"] = now
    return False


def is_network_error_message(message: str) -> bool:
    """Heuristic: does the git stderr look like a network failure?"""
    lower = message.lower()
    return any(kw in lower for kw in _NETWORK_ERROR_KEYWORDS)


def ensure_internet_or_raise(timeout: float = 3.0) -> None:
    """Raise GitManagerError with message if offline."""
    # Local import to avoid circular dependency at module load time
    from core.git_operations import GitManagerError  # noqa: WPS433

    if not has_internet_connection(timeout=timeout):
        raise GitManagerError(f"{NO_INTERNET_MSG} — {NO_INTERNET_DETAIL}")
