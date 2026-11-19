"""
Access code for testing over a local network.

When the server is reachable from other devices (DNT_HOST is not 127.0.0.1), an
access code is required before any API call is accepted. The code is shown on the
laptop screen when the server starts; the iPad types it in once and gets a cookie
that lasts 12 hours. This keeps other people on the same Wi-Fi from using the app.

It is a simple shared code for testing, not a full login system. Teacher and
student accounts are a later stage.
"""
import hmac
import hashlib
import os
import secrets
import socket

HEADER_NAME = "X-Access-Code"
COOKIE_NAME = "dnt_access"

# Paths that work without the code: the page, its files, health, and the login itself.
PUBLIC_PREFIXES = ("/app", "/health", "/auth", "/favicon")
PUBLIC_EXACT = {"/", "/pixform"}

_SECRET = secrets.token_bytes(32)  # new each server start, so old cookies stop working


def _code() -> str:
    return os.getenv("DNT_ACCESS_CODE", "").strip()


def is_required() -> bool:
    return bool(_code())


def is_public_path(path: str) -> bool:
    return path in PUBLIC_EXACT or path.startswith(PUBLIC_PREFIXES)


def code_matches(candidate: str) -> bool:
    code = _code()
    return bool(code) and hmac.compare_digest(str(candidate or "").strip().upper(), code.upper())


def session_token() -> str:
    return hmac.new(_SECRET, _code().upper().encode(), hashlib.sha256).hexdigest()


def request_has_access(request) -> bool:
    if code_matches(request.headers.get(HEADER_NAME, "")):
        return True
    cookie = request.cookies.get(COOKIE_NAME, "")
    return bool(cookie) and hmac.compare_digest(cookie, session_token())


def _is_loopback(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def local_ip_addresses():
    """Best guess at this computer's addresses on the local network (no internet needed)."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:  # finds the address of the main network adapter; nothing is actually sent
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


def announce(host: str, port: int, logger) -> None:
    """Print how to open the app. On a network-visible server, make sure a code exists."""
    if _is_loopback(host):
        logger.info("Open the app on this computer: http://localhost:%s", port)
        logger.info("(Only this computer can connect. To test from an iPad, start with the --lan option.)")
        return
    if not _code():
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I mix-ups
        os.environ["DNT_ACCESS_CODE"] = "".join(secrets.choice(alphabet) for _ in range(6))
    bar = "=" * 62
    logger.info(bar)
    logger.info("  D&T Sketch-to-3D is reachable from other devices on this network")
    for ip in local_ip_addresses() or ["<this laptop's IP address>"]:
        logger.info("  On the iPad, open Safari and go to:  http://%s:%s", ip, port)
    logger.info("  Access code:  %s", _code())
    logger.info("  Stop the server: press Ctrl+C in this window.")
    logger.info(bar)
