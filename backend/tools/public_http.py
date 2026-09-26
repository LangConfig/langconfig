"""HTTP transport for untrusted tool URLs, restricted to public destinations.

Checks belong at TCP connection time: prechecking a URL and letting the HTTP
client resolve it again permits DNS rebinding. Resolve all addresses once,
validate every answer, and connect to a numeric address from that result. Keep
the original HTTP origin so Host, TLS SNI, and certificate verification retain
their normal behavior. Redirects use the same connection pool and policy.
"""

from contextlib import contextmanager
from ipaddress import ip_address, ip_network
import socket

import anyio
import httpcore
import httpx


class OutboundHTTPBlocked(httpx.RequestError):
    """An untrusted URL cannot be contacted under the public-network policy."""


_TRANSLATION_NETWORKS = (
    ip_network("64:ff9b::/96"),
    ip_network("64:ff9b:1::/48"),
)


def _public_address(value: str) -> str:
    if "%" in value:
        raise OutboundHTTPBlocked("Outbound HTTP blocked: scoped IP addresses are not allowed")
    try:
        address = ip_address(value)
    except ValueError as exc:
        raise OutboundHTTPBlocked("Outbound HTTP blocked: invalid resolved address") from exc
    if address.version == 6 and address.ipv4_mapped:
        return _public_address(str(address.ipv4_mapped))
    if (
        not address.is_global
        or address.is_multicast
        or address.is_reserved
        or address.is_loopback
        or address.is_link_local
        or address.is_unspecified
    ):
        raise OutboundHTTPBlocked("Outbound HTTP blocked: destination is not a public address")
    if address.version == 6:
        # Transition/translation mechanisms can embed a non-public IPv4 target.
        if address.sixtofour or address.teredo or any(
            address in network for network in _TRANSLATION_NETWORKS
        ):
            raise OutboundHTTPBlocked("Outbound HTTP blocked: IPv6 transition addresses are not allowed")
    return str(address)


class PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    """Resolve and pin each TCP connection; never delegate a hostname lookup."""

    def __init__(self):
        self._backend = httpcore.AnyIOBackend()

    async def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ):
        try:
            with anyio.fail_after(timeout):
                if "%" in host:
                    raise OutboundHTTPBlocked("Outbound HTTP blocked: scoped host is not allowed")
                try:
                    literal = ip_address(host)
                except ValueError:
                    literal = None
                if literal is not None:
                    addresses = [_public_address(str(literal))]
                else:
                    try:
                        answers = await anyio.getaddrinfo(host, port, type=socket.SOCK_STREAM)
                    except OSError as exc:
                        raise OutboundHTTPBlocked("Outbound HTTP blocked: DNS resolution failed") from exc
                    addresses = []
                    for family, _, _, _, sockaddr in answers:
                        if family not in (socket.AF_INET, socket.AF_INET6):
                            raise OutboundHTTPBlocked("Outbound HTTP blocked: unsupported address family")
                        address = _public_address(sockaddr[0])
                        if address not in addresses:
                            addresses.append(address)
                    if not addresses:
                        raise OutboundHTTPBlocked("Outbound HTTP blocked: DNS returned no addresses")

                # Every answer is checked before any connection is attempted.
                last_error = None
                for address in addresses:
                    try:
                        return await self._backend.connect_tcp(
                            address, port, timeout=timeout,
                            local_address=local_address, socket_options=socket_options,
                        )
                    except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                        last_error = exc
                raise last_error
        except TimeoutError as exc:
            raise httpcore.ConnectTimeout("Timed out resolving or connecting to public destination") from exc

    async def connect_unix_socket(self, *args, **kwargs):
        raise OutboundHTTPBlocked("Outbound HTTP blocked: Unix sockets are not allowed")

    async def sleep(self, seconds):
        await anyio.sleep(seconds)


@contextmanager
def _http_errors():
    """Preserve HTTPX's error contract when adapting the public HTTPCore API."""
    try:
        yield
    except httpcore.TimeoutException as exc:
        raise httpx.TimeoutException(str(exc)) from exc
    except httpcore.NetworkError as exc:
        raise httpx.NetworkError(str(exc)) from exc
    except httpcore.ProtocolError as exc:
        raise httpx.ProtocolError(str(exc)) from exc
    except httpcore.UnsupportedProtocol as exc:
        raise httpx.UnsupportedProtocol(str(exc)) from exc


class _ResponseStream(httpx.AsyncByteStream):
    def __init__(self, stream):
        self._stream = stream

    async def __aiter__(self):
        with _http_errors():
            async for chunk in self._stream:
                yield chunk

    async def aclose(self):
        with _http_errors():
            await self._stream.aclose()


class PublicHTTPTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=httpcore.default_ssl_context(),
            network_backend=PublicNetworkBackend(),
        )

    async def handle_async_request(self, request):
        if (
            request.url.scheme not in ("http", "https")
            or not request.url.host
            or request.url.userinfo
            or "%" in request.url.host
        ):
            raise OutboundHTTPBlocked("Outbound HTTP blocked: invalid URL, credentials, or scheme")
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        with _http_errors():
            response = await self._pool.handle_async_request(core_request)
        return httpx.Response(
            status_code=response.status,
            headers=response.headers,
            stream=_ResponseStream(response.stream),
            extensions=response.extensions,
        )

    async def aclose(self):
        with _http_errors():
            await self._pool.aclose()


def public_http_client(timeout: float) -> httpx.AsyncClient:
    # A proxy could resolve destinations itself, bypassing the pinned backend.
    return httpx.AsyncClient(
        transport=PublicHTTPTransport(), timeout=timeout,
        follow_redirects=True, trust_env=False,
    )
