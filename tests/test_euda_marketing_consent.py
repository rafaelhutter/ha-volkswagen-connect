"""Self-check: VW's optional marketing-consent page must not fail the EU Data Act login (#34).

Run inside the HA container (needs aiohttp + bs4): python3 tests/test_euda_marketing_consent.py
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "custom_components/volkswagen_connect/eu_data_act.py"
_spec = importlib.util.spec_from_file_location("eu_data_act", _SRC)
eu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eu)

IDENTITY = "https://identity.vwgroup.io"
CLIENT = eu.BRAND_CLIENT_IDS[eu.DEFAULT_BRAND]
PORTAL_HOME = f"{eu.BASE_URL}/de/en/user.html"
CALLBACK = f"{IDENTITY}/oidc/v1/oauth/client/callback?scopes=openid cars profile&hmac=abc"
MARKETING = (
    f"{IDENTITY}/signin-service/v1/consent/marketing/user-1/{CLIENT}"
    "?callback=https%3A%2F%2Fidentity.vwgroup.io%2Foidc%2Fv1%2Foauth%2Fclient%2Fcallback"
    "%3Fscopes%3Dopenid%2520cars%2520profile%26hmac%3Dabc&relayState=r1"
)
REAL_CONSENT = f"{IDENTITY}/signin-service/v1/consent/users/user-1/{CLIENT}?scopes=openid&relayState=r1"
LOGIN_FORM = '<form action="{action}"><input name="hmac" value="h"><input name="_csrf" value="c"></form>'


class _Response:
    def __init__(self, url: str, body: str = "") -> None:
        self.url = url
        self._body = body

    async def text(self) -> str:
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __await__(self):  # the priming GET is awaited, not entered
        async def _self():
            return self

        return _self().__await__()


class _Session:
    """VW's login as the portal sees it; the password step lands on ``after_password``."""

    def __init__(self, after_password: str) -> None:
        self.after_password = after_password
        self.gets: list[str] = []

    def get(self, url: str, **_):
        self.gets.append(url)
        if "oauth/client/callback" in url:
            return _Response(PORTAL_HOME)
        if url.startswith(eu.OIDC_AUTHORIZE_URL):
            page = f"{IDENTITY}/signin-service/v1/{CLIENT}/login/identifier"
            return _Response(page, LOGIN_FORM.format(action="identifier"))
        return _Response(url)

    def post(self, url: str, data=None, **_):
        if url.endswith("/identifier"):
            page = f"{IDENTITY}/signin-service/v1/{CLIENT}/login/authenticate"
            return _Response(page, LOGIN_FORM.format(action="authenticate"))
        return _Response(self.after_password)


def _login(after_password: str) -> tuple[eu.EuDataActClient, _Session]:
    session = _Session(after_password)
    client = eu.EuDataActClient(session, "a@b.c", "pw")
    asyncio.run(client.login())
    return client, session


def test_marketing_page_is_skipped_through_its_callback() -> None:
    client, session = _login(MARKETING)
    assert client._logged_in
    followed = [url for url in session.gets if "oauth/client/callback" in url]
    expected = f"{IDENTITY}/oidc/v1/oauth/client/callback?scopes=openid+cars+profile&hmac=abc"
    assert followed == [expected], followed


def test_real_consent_screen_still_asks_for_the_browser() -> None:
    try:
        _login(REAL_CONSENT)
    except eu.EuDataActAuthError as err:
        assert err.reason == "not_authorised", err.reason
    else:
        raise AssertionError("a real consent screen must not log in")


def test_callback_only_for_marketing_pages() -> None:
    assert eu._marketing_consent_callback(REAL_CONSENT) is None
    assert eu._marketing_consent_callback(PORTAL_HOME) is None
    assert eu._marketing_consent_callback(MARKETING.split("?")[0]) is None  # no callback to follow
    assert eu._marketing_consent_callback(MARKETING).startswith(CALLBACK.split("?")[0])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall checks passed")
