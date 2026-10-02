"""Self-check for the HTTP/2 portal session. Run: python3 tests/test_http2_session.py"""

import asyncio
import importlib.util
from pathlib import Path

import aiohttp
import httpx

# Load the module by path: importing the package would pull in homeassistant.
_SRC = Path(__file__).resolve().parents[1] / "custom_components/volkswagen_connect/http2_session.py"
_spec = importlib.util.spec_from_file_location("http2_session", _SRC)
h2s = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h2s)

PORTAL = "https://www.volkswagen.de"
IDENTITY = "https://identity.vwgroup.io"


def handler(req):
    path, cookie = req.url.path, req.headers.get("cookie", "")
    if path == "/start":
        return httpx.Response(302, headers={
            "location": IDENTITY + "/authorize", "set-cookie": "SESSION=s1; Path=/; Secure"})
    if path == "/authorize":
        assert "SESSION" not in cookie, cookie
        return httpx.Response(302, headers={"location": "/u/login", "set-cookie": "auth0=a1; Path=/; Secure"})
    if path == "/u/login":
        assert cookie == "auth0=a1", cookie
        return httpx.Response(302, headers={"location": PORTAL + "/landing"})
    if path == "/landing":
        assert cookie == "SESSION=s1", cookie
        return httpx.Response(200, text="landed")
    if path == "/loop":
        return httpx.Response(302, headers={"location": "/loop"})
    if path == "/form":
        return httpx.Response(302, headers={"location": "/echo"})
    if path == "/echo":
        return httpx.Response(200, text=f"{req.method}:{req.content.decode()}")
    raise httpx.ConnectError("unreachable", request=req)


async def main():
    s = h2s.Http2Session(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    # cross-host redirect chain: each host only gets its own cookies
    async with s.get(PORTAL + "/start", max_redirects=30) as r:
        assert r.status == 200 and str(r.url) == PORTAL + "/landing", r.url
        assert await r.text() == "landed"
    jar = sorted((c["domain"], c.key) for c in s.cookie_jar)
    assert jar == [("identity.vwgroup.io", "auth0"), ("www.volkswagen.de", "SESSION")], jar
    assert not s._client.cookies

    async with s.get(PORTAL + "/start", allow_redirects=False) as r:
        assert r.status == 302 and r.headers.get("Location") == IDENTITY + "/authorize"

    async with s.post(PORTAL + "/form", data={"a": "1"}) as r:
        assert await r.text() == "GET:"

    try:
        async with s.get(PORTAL + "/loop", max_redirects=5):
            pass
        raise AssertionError("expected TooManyRedirects")
    except aiohttp.TooManyRedirects as err:
        assert len(err.history) == 5 and str(err.history[-1].url) == PORTAL + "/loop"
        str(err)

    try:
        async with s.get(PORTAL + "/down"):
            pass
        raise AssertionError("expected ClientError")
    except aiohttp.ClientError:
        pass

    print("ok")


asyncio.run(main())
