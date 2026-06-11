# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Tests for the get_current_time and http_request native agent tools.

All http_request tests use httpx.MockTransport via a monkeypatched
_get_http_client factory - no network access.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

# Ensure backend/ is importable regardless of how pytest is invoked
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import tools.native_tools as native_tools
from tools.native_tools import get_current_time, http_request, load_native_tools

WEEKDAYS = {
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
}


# =============================================================================
# get_current_time
# =============================================================================

def test_get_current_time_utc_contains_today():
    result = get_current_time.invoke({"timezone": "UTC"})
    assert isinstance(result, str)
    today = datetime.now(ZoneInfo("UTC")).date().isoformat()
    assert today in result
    assert "UTC" in result
    assert any(day in result for day in WEEKDAYS)


def test_get_current_time_default_is_utc():
    result = get_current_time.invoke({})
    assert "UTC" in result
    assert not result.startswith("Error")


def test_get_current_time_respects_timezone():
    result = get_current_time.invoke({"timezone": "America/New_York"})
    assert "America/New_York" in result
    expected_date = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    assert expected_date in result
    # ISO-8601 offset for New York is -04:00 (EDT) or -05:00 (EST)
    assert "-04:00" in result or "-05:00" in result


def test_get_current_time_invalid_timezone_returns_error_string():
    result = get_current_time.invoke({"timezone": "Not/AZone"})
    assert isinstance(result, str)
    assert result.startswith("Error")
    assert "Not/AZone" in result
    assert "IANA" in result


# =============================================================================
# http_request - input validation (no transport needed)
# =============================================================================

@pytest.mark.asyncio
async def test_http_request_rejects_file_scheme():
    result = await http_request.ainvoke({"url": "file:///etc/passwd"})
    assert result.startswith("Error")
    assert "http" in result.lower()


@pytest.mark.asyncio
async def test_http_request_rejects_ftp_scheme():
    result = await http_request.ainvoke({"url": "ftp://example.com/file.txt"})
    assert result.startswith("Error")


@pytest.mark.asyncio
async def test_http_request_rejects_body_on_get():
    result = await http_request.ainvoke({
        "url": "https://example.com/api",
        "method": "GET",
        "body": '{"key": "value"}',
    })
    assert result.startswith("Error")
    assert "GET" in result


@pytest.mark.asyncio
async def test_http_request_rejects_body_on_head():
    result = await http_request.ainvoke({
        "url": "https://example.com/api",
        "method": "HEAD",
        "body": "payload",
    })
    assert result.startswith("Error")


@pytest.mark.asyncio
async def test_http_request_rejects_disallowed_method():
    result = await http_request.ainvoke({
        "url": "https://example.com/api",
        "method": "TRACE",
    })
    assert result.startswith("Error")
    assert "TRACE" in result


# =============================================================================
# http_request - mocked transport
# =============================================================================

def _patch_transport(monkeypatch, handler):
    """Route _get_http_client through an httpx.MockTransport."""
    def factory(timeout):
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler), timeout=timeout
        )
    monkeypatch.setattr(native_tools, "_get_http_client", factory)


@pytest.mark.asyncio
async def test_http_request_json_pretty_print(monkeypatch):
    payload = {"name": "langconfig", "nested": {"count": 3}}

    def handler(request):
        return httpx.Response(200, json=payload)

    _patch_transport(monkeypatch, handler)
    result = await http_request.ainvoke({"url": "https://api.example.com/info"})

    assert "200" in result
    # Pretty-printed JSON has indented keys on their own lines
    assert '"name": "langconfig"' in result
    assert '  "nested": {' in result
    assert "Truncated" not in result and "truncated" not in result


@pytest.mark.asyncio
async def test_http_request_post_sends_body(monkeypatch):
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["body"] = request.content.decode()
        return httpx.Response(201, json={"created": True})

    _patch_transport(monkeypatch, handler)
    result = await http_request.ainvoke({
        "url": "https://api.example.com/items",
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"a": 1}),
    })

    assert seen["method"] == "POST"
    assert seen["body"] == '{"a": 1}'
    assert "201" in result
    assert not result.startswith("Error")


@pytest.mark.asyncio
async def test_http_request_truncates_long_responses(monkeypatch):
    long_body = "x" * 1000

    def handler(request):
        return httpx.Response(200, text=long_body)

    _patch_transport(monkeypatch, handler)
    result = await http_request.ainvoke({
        "url": "https://api.example.com/big",
        "max_chars": 100,
    })

    assert "truncated" in result.lower()
    # Body portion is clipped: full 1000-char run must not appear
    assert long_body not in result


@pytest.mark.asyncio
async def test_http_request_connection_error_returns_string(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("connection refused")

    _patch_transport(monkeypatch, handler)
    result = await http_request.ainvoke({"url": "https://api.example.com/down"})
    assert isinstance(result, str)
    assert result.startswith("Error")


# =============================================================================
# Registry
# =============================================================================

def test_load_native_tools_returns_both_new_tools():
    loaded = load_native_tools(["http_request", "get_current_time"])
    assert len(loaded) == 2
    names = {t.name for t in loaded}
    assert names == {"http_request", "get_current_time"}


def test_new_tools_in_available_tool_names():
    from tools.native_tools import get_available_tool_names
    names = get_available_tool_names()
    assert "http_request" in names
    assert "get_current_time" in names


def test_aliases_load_canonical_tools():
    loaded = load_native_tools(["fetch_api", "current_time"])
    assert len(loaded) == 2
    names = {t.name for t in loaded}
    assert names == {"http_request", "get_current_time"}
