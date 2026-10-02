"""Fail-closed trust boundary for experimental local-only APIs."""

from ipaddress import ip_address

from fastapi import HTTPException, Request, status

from config import settings

EXPERIMENTAL_API_RESPONSES = {
    status.HTTP_403_FORBIDDEN: {
        "description": "Experimental local APIs are disabled or the caller is not loopback-local."
    }
}


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        address = ip_address(host)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    mapped = getattr(address, "ipv4_mapped", None)
    return bool(mapped and mapped.is_loopback)


def require_experimental_local_api(request: Request) -> None:
    """Allow experimental APIs only when opted in and called via loopback."""
    if not settings.enable_experimental_local_apis:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Experimental local APIs are disabled",
        )

    client_host = request.client.host if request.client else ""
    if not _is_loopback_host(client_host):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Experimental APIs accept loopback requests only",
        )
