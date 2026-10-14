"""Self-check: VW's advertising opt-in page must not break the portal login.

Run inside the HA container (needs aiohttp + bs4): python3 tests/test_portal_data_clean_room.py
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "custom_components/volkswagen_connect/website_portal.py"
_spec = importlib.util.spec_from_file_location("website_portal", _SRC)
wp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wp)

CONSENT = "https://consent.vwgroup.io"
PAGE_URL = f"{CONSENT}/hooks/data-clean-room?session=s1&state=st"
SKIP = f"{CONSENT}/hooks/data-clean-room/skip?session=s1&state=st"
ACCEPT = f"{CONSENT}/hooks/data-clean-room/accept?session=s1&state=st"
CONTINUE = "https://identity.vwgroup.io/v1/action-hooks/flows/continue?state=st"
CODE = "https://www.volkswagen.de/app/authproxy/login/oauth2/code/vw-de?code=c"
PORTAL_OK = "https://www.volkswagen.de/de/besitzer-und-nutzer/myvolkswagen.html"
PAGE = (
    "<html><body><h1>Personalised advertising tailored to your requirements</h1>"
    '<a href="/hooks/data-clean-room/accept?session=s1&amp;state=st">Consent</a>'
    '<a href="/hooks/data-clean-room/skip?session=s1&amp;state=st">Not now</a>'
    "</body></html>"
)


class _Response:
    def __init__(self, status: int, url: str, location: str | None = None, body: str = "") -> None:
        self.status = status
        self.url = url
        self.headers = {"Location": location} if location else {}
        self._body = body

    async def text(self) -> str:
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Session:
    def __init__(self) -> None:
        self.gets: list[str] = []
        self.cookie_jar = ()

    def get(self, url: str, allow_redirects: bool = True, **_):
        self.gets.append(url)
        if url == wp.AUTHPROXY_LOGIN and allow_redirects:
            return _Response(200, PAGE_URL, body=PAGE)
        hops = {SKIP: CONTINUE, CONTINUE: CODE, CODE: PORTAL_OK}
        if url in hops:
            return _Response(302, url, location=hops[url])
        return _Response(200, url)


def test_skip_link_is_the_not_now_button() -> None:
    assert wp._data_clean_room_skip(PAGE_URL, PAGE) == SKIP


def test_only_the_advertising_page_is_skipped() -> None:
    assert wp._data_clean_room_skip(PORTAL_OK, PAGE) is None
    assert wp._data_clean_room_skip(PAGE_URL, "<html></html>") is None


def test_silent_refresh_heals_through_the_advertising_page() -> None:
    session = _Session()
    client = wp.WebsitePortalClient(session, "a@b.c", "pw")
    asyncio.run(client.refresh())
    assert SKIP in session.gets, session.gets
    assert ACCEPT not in session.gets, session.gets


def test_silent_login_heals_through_the_advertising_page() -> None:
    session = _Session()
    client = wp.WebsitePortalClient(session, "a@b.c", "pw")
    assert asyncio.run(client.begin_login()) == "ok"
    assert ACCEPT not in session.gets, session.gets


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall checks passed")
