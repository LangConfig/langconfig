"""Outbound policy regressions: no external services or real Codex calls."""

import asyncio
from contextlib import asynccontextmanager
import json
import socket
import ssl
from ipaddress import ip_address

import anyio
from fastapi import FastAPI
import httpcore
import httpx
import pytest
import uvicorn

from api.codex import routes as codex_routes
from config import settings
from tools import native_tools
from tools.public_http import OutboundHTTPBlocked, public_http_client


@asynccontextmanager
async def local_codex_api(monkeypatch):
    calls = []

    class FakeHarness:
        def start_exec_run(self, prompt, **kwargs):
            calls.append(prompt)
            return {"id": "no-real-process"}

        def serialize_run(self, run):
            return run

        def status(self):
            calls.append("status")
            return {"installed": True}

    monkeypatch.setattr(settings, "enable_experimental_local_apis", True)
    monkeypatch.setattr(codex_routes, "codex_harness", FakeHarness())
    app = FastAPI()
    app.include_router(codex_routes.router)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", lifespan="off", ws="none"))
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(5):
            while not server.started:
                if task.done():
                    await task
                    raise AssertionError("Test API stopped before startup")
                await asyncio.sleep(0.01)
        yield port, calls
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=5)
        finally:
            listener.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["http_request", "web_fetch"])
@pytest.mark.parametrize("hostname", ["127.0.0.1", "localhost", "127.1", "2130706433", "0x7f000001"])
async def test_native_tools_cannot_reach_opted_in_local_codex_api(monkeypatch, tool_name, hostname):
    async with local_codex_api(monkeypatch) as (port, calls):
        tool = native_tools.load_native_tools([tool_name])[0]
        if tool_name == "http_request":
            args = {
                "url": f"http://{hostname}:{port}/api/codex/runs",
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"prompt": "must not start"}),
            }
        else:
            args = {"url": f"http://{hostname}:{port}/api/codex/status"}
        result = await tool.ainvoke(args)

        assert calls == [], "The generic tool bypassed the protected tool's approval"
        assert result.startswith("Error")
        assert "blocked" in result.lower()


class WireStream(httpcore.AsyncMockStream):
    def __init__(self, response):
        super().__init__([response])
        self.writes = []
        self.tls = []
        self.closed = False

    async def write(self, buffer, timeout=None):
        self.writes.append(buffer)

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        self.tls.append((server_hostname, ssl_context))
        return self

    async def aclose(self):
        self.closed = True
        await super().aclose()


def wire_network(monkeypatch, records, responses=None):
    """Fake only DNS/TCP IO; retain real tools, policy, HTTP and redirect logic."""
    lookups, connections, streams = [], [], []
    responses = list(responses or [
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 6\r\nConnection: close\r\n\r\npublic"
    ])

    async def resolve(host, port, **kwargs):
        lookups.append(host)
        addresses = records(host) if callable(records) else records[host]
        if isinstance(addresses, Exception):
            raise addresses
        return [
            (socket.AF_INET6 if ip_address(address).version == 6 else socket.AF_INET,
             socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))
            for address in addresses
        ]

    async def connect(self, host, port, **kwargs):
        # The delegate must receive a validated numeric address, never a hostname.
        assert ip_address(host).is_global
        connections.append((host, port))
        stream = WireStream(responses.pop(0))
        streams.append(stream)
        return stream

    monkeypatch.setattr(anyio, "getaddrinfo", resolve)
    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)
    return lookups, connections, streams


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["http_request", "web_fetch"])
@pytest.mark.parametrize("scheme", ["http", "https"])
@pytest.mark.parametrize("address", ["93.184.215.14", "2606:4700:4700::1111"])
async def test_public_requests_preserve_body_host_tls_and_close(monkeypatch, tool_name, scheme, address):
    lookups, connections, streams = wire_network(monkeypatch, {"public.example": [address]})
    # Environment proxies must not bypass our connection-time policy.
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    args = {"url": f"{scheme}://public.example/path"}
    if tool_name == "http_request":
        args.update(method="POST", body='{"public":true}', headers={"Content-Type": "application/json"})
    result = await getattr(native_tools, tool_name).ainvoke(args)

    assert "public" in result
    assert not result.startswith("Error")
    assert lookups == ["public.example"]
    assert connections == [(address, 443 if scheme == "https" else 80)]
    wire = b"".join(streams[0].writes)
    assert b"Host: public.example\r\n" in wire
    if tool_name == "http_request":
        assert b'{"public":true}' in wire
    if scheme == "https":
        hostname, context = streams[0].tls[0]
        assert hostname == "public.example"
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED
    assert all(stream.closed for stream in streams)


@pytest.mark.asyncio
@pytest.mark.parametrize("address", [
    "0.0.0.0", "10.1.2.3", "127.0.0.1", "169.254.169.254", "172.16.0.1",
    "192.168.1.1", "100.64.0.1", "192.0.2.1", "198.18.0.1", "224.0.0.1", "255.255.255.255",
    "::", "::1", "fc00::1", "fe80::1", "ff02::1", "2001:db8::1",
    "::ffff:127.0.0.1", "::ffff:10.1.2.3", "64:ff9b::7f00:1", "2002:7f00:1::",
])
async def test_nonpublic_literal_addresses_never_connect(monkeypatch, address):
    lookups, connections, _ = wire_network(monkeypatch, {})
    hostname = f"[{address}]" if ":" in address else address
    result = await native_tools.http_request.ainvoke({"url": f"http://{hostname}/"})
    assert result.startswith("Error")
    assert "blocked" in result.lower()
    assert lookups == connections == []


@pytest.mark.asyncio
@pytest.mark.parametrize("addresses", [
    ["10.1.2.3"], ["::1"], ["::ffff:127.0.0.1"],
    ["93.184.215.14", "127.0.0.1"], ["127.0.0.1", "93.184.215.14"],
])
async def test_every_dns_answer_must_be_public_before_connecting(monkeypatch, addresses):
    _, connections, _ = wire_network(monkeypatch, {"private.example": addresses})
    result = await native_tools.web_fetch.ainvoke({"url": "https://private.example/"})
    assert result.startswith("Error")
    assert "blocked" in result.lower()
    assert connections == []


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", [[], socket.gaierror("unresolved")])
async def test_resolution_failures_fail_closed(monkeypatch, answer):
    _, connections, _ = wire_network(monkeypatch, {"missing.example": answer})
    result = await native_tools.http_request.ainvoke({"url": "https://missing.example/"})
    assert result.startswith("Error")
    assert "blocked" in result.lower()
    assert connections == []


@pytest.mark.asyncio
async def test_public_ipv4_mapped_dns_answer_is_pinned_to_ipv4(monkeypatch):
    _, connections, _ = wire_network(monkeypatch, {"mapped.example": ["::ffff:93.184.215.14"]})
    result = await native_tools.web_fetch.ainvoke({"url": "https://mapped.example/"})
    assert result == "public"
    assert connections == [("93.184.215.14", 443)]


@pytest.mark.asyncio
async def test_dns_resolution_obeys_connection_timeout(monkeypatch):
    async def stalled_dns(*args, **kwargs):
        await anyio.sleep_forever()

    monkeypatch.setattr(anyio, "getaddrinfo", stalled_dns)
    async with public_http_client(0.01) as client:
        with pytest.raises(httpx.TimeoutException):
            await client.get("https://stalled.example/")


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["http_request", "web_fetch"])
@pytest.mark.parametrize("redirect_host", ["127.0.0.1", "private.example", "[::1]"])
async def test_redirects_cannot_reach_local_api(monkeypatch, tool_name, redirect_host):
    async with local_codex_api(monkeypatch) as (port, calls):
        response = (
            "HTTP/1.1 307 Temporary Redirect\r\n"
            f"Location: http://{redirect_host}:{port}/api/codex/status\r\n"
            "Content-Length: 0\r\nConnection: close\r\n\r\n"
        ).encode()
        _, connections, streams = wire_network(monkeypatch, {
            "public.example": ["93.184.215.14"], "private.example": ["127.0.0.1"],
        }, [response])
        result = await getattr(native_tools, tool_name).ainvoke({"url": "https://public.example/redirect"})
        assert result.startswith("Error")
        assert "blocked" in result.lower()
        assert connections == [("93.184.215.14", 443)]
        assert calls == []
        assert all(stream.closed for stream in streams)


@pytest.mark.asyncio
async def test_public_redirects_still_work(monkeypatch):
    lookups, connections, streams = wire_network(monkeypatch, {
        "first.example": ["93.184.215.14"], "second.example": ["1.1.1.1"],
    }, [
        b"HTTP/1.1 302 Found\r\nLocation: https://second.example/end\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 6\r\nConnection: close\r\n\r\npublic",
    ])
    assert await native_tools.web_fetch.ainvoke({"url": "https://first.example/start"}) == "public"
    assert lookups == ["first.example", "second.example"]
    assert connections == [("93.184.215.14", 443), ("1.1.1.1", 443)]
    assert all(stream.closed for stream in streams)


@pytest.mark.asyncio
async def test_dns_rebinding_is_pinned_and_rechecked_on_next_connection(monkeypatch):
    answers = iter([["93.184.215.14"], ["127.0.0.1"]])
    lookups, connections, streams = wire_network(monkeypatch, lambda host: next(answers))
    async with public_http_client(2) as client:
        assert (await client.get("https://changing.example/first")).text == "public"
        with pytest.raises(OutboundHTTPBlocked, match="blocked"):
            await client.get("https://changing.example/second")
    assert lookups == ["changing.example", "changing.example"]
    assert connections == [("93.184.215.14", 443)]
    assert all(stream.closed for stream in streams)


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "ftp://public.example/file", "file:///etc/passwd", "http:///path",
    "http://name:secret@public.example/", "http://[fe80::1%25eth0]/", "http://bad%00host/",
])
async def test_invalid_schemes_hosts_and_credentials_never_resolve_or_connect(monkeypatch, url):
    lookups, connections, _ = wire_network(monkeypatch, {})
    result = await native_tools.web_fetch.ainvoke({"url": url})
    assert result.startswith("Error")
    assert lookups == connections == []
