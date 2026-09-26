import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.codex.routes import router as codex_router
from api.experimental_local import require_experimental_local_api
from api.hermes.routes import router as hermes_router
from api.platform_brain.routes import router as platform_brain_router
from config import settings


def _request_from(host: str) -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": (host, 12345),
        "server": ("127.0.0.1", 8780),
        "scheme": "http",
        "query_string": b"",
    })


def test_experimental_local_apis_fail_closed_by_default(monkeypatch):
    monkeypatch.setattr(settings, "enable_experimental_local_apis", False)

    with pytest.raises(HTTPException) as exc_info:
        require_experimental_local_api(_request_from("127.0.0.1"))

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_experimental_local_apis_allow_enabled_loopback(monkeypatch, host):
    monkeypatch.setattr(settings, "enable_experimental_local_apis", True)

    require_experimental_local_api(_request_from(host))


def test_experimental_local_apis_reject_enabled_non_loopback(monkeypatch):
    monkeypatch.setattr(settings, "enable_experimental_local_apis", True)

    with pytest.raises(HTTPException) as exc_info:
        require_experimental_local_api(_request_from("192.0.2.10"))

    assert exc_info.value.status_code == 403


def test_experimental_routers_share_the_fail_closed_dependency():
    for router in (codex_router, hermes_router, platform_brain_router):
        dependencies = [dependency.dependency for dependency in router.dependencies]
        assert require_experimental_local_api in dependencies
