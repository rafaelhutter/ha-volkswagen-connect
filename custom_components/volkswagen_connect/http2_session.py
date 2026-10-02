"""HTTP/2 stand-in for the aiohttp session WebsitePortalClient uses."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http.cookies import CookieError, SimpleCookie
from typing import Any

import aiohttp
import httpx
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL


def create_client(hass: Any) -> httpx.AsyncClient:
    """HTTP/2 client from Home Assistant's httpx helper."""
    from homeassistant.helpers.httpx_client import create_async_httpx_client

    kwargs: dict[str, Any] = {"follow_redirects": False, "timeout": 30}
    try:
        from homeassistant.util.ssl import SSL_ALPN_HTTP11_HTTP2
    except ImportError:  # HA < 2026.2
        return create_async_httpx_client(hass, http2=True, **kwargs)
    return create_async_httpx_client(hass, alpn_protocols=SSL_ALPN_HTTP11_HTTP2, **kwargs)


class Http2Response:
    """The aiohttp.ClientResponse subset the portal reads."""

    def __init__(self, resp: httpx.Response) -> None:
        self._resp = resp
        self.status = resp.status_code
        self.headers = resp.headers
        self.url = URL(str(resp.url))

    async def text(self) -> str:
        return self._resp.text


class Http2Session:
    """aiohttp.ClientSession look-alike; cookies stay in an aiohttp.CookieJar."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self.cookie_jar = aiohttp.CookieJar()

    @asynccontextmanager
    async def get(self, url: str, **kwargs: Any) -> AsyncIterator[Http2Response]:
        yield await self._request("GET", url, **kwargs)

    @asynccontextmanager
    async def post(self, url: str, **kwargs: Any) -> AsyncIterator[Http2Response]:
        yield await self._request("POST", url, **kwargs)

    async def _send(
        self, method: str, url: str, headers: dict[str, str], data: Any
    ) -> httpx.Response:
        jar = self.cookie_jar.filter_cookies(URL(url))
        if jar:
            headers = {**headers, "Cookie": "; ".join(f"{k}={m.value}" for k, m in jar.items())}
        try:
            resp = await self._client.request(method, url, headers=headers, data=data)
        except httpx.HTTPError as err:
            raise aiohttp.ClientError(f"{type(err).__name__}: {err}") from err
        finally:
            self._client.cookies.clear()
        for raw in resp.headers.get_list("set-cookie"):
            cookie: SimpleCookie = SimpleCookie()
            try:
                cookie.load(raw)
            except CookieError:
                continue
            self.cookie_jar.update_cookies(cookie, URL(str(resp.url)))
        return resp

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: Any = None,
        allow_redirects: bool = True,
        max_redirects: int = 10,
    ) -> Http2Response:
        headers = headers or {}
        resp = await self._send(method, url, headers, data)
        history: list[Http2Response] = []
        while allow_redirects and resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if not location:
                break
            history.append(Http2Response(resp))
            if len(history) >= max_redirects:
                info = aiohttp.RequestInfo(
                    URL(url), method, CIMultiDictProxy(CIMultiDict()), URL(url)
                )
                raise aiohttp.TooManyRedirects(info, tuple(history))
            if resp.status_code not in (307, 308):
                method, data = "GET", None
            url = str(resp.url.join(location))
            resp = await self._send(method, url, headers, data)
        return Http2Response(resp)
