"""Self-check: the portal session is only renewed when a data call finds it stale.

Needs the integration's deps, so run it inside the HA container:
    python3 tests/test_portal_lazy_refresh.py
"""

from __future__ import annotations

import asyncio
import pathlib
import sys
from datetime import UTC, datetime
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
# homeassistant aliases httpx on import, so it has to come before ours.
from custom_components.volkswagen_connect import coordinator as co  # noqa: E402
from custom_components.volkswagen_connect import website_portal as wp  # noqa: E402
from custom_components.volkswagen_connect.http2_session import Http2Session  # noqa: E402
from homeassistant.exceptions import ConfigEntryAuthFailed  # noqa: E402

import httpx  # noqa: E402

VIN = "WVWZZZ00000000001"
NOW = 1_000_000.0
IDENTITY = "https://identity.vwgroup.io"
MFA_EXPIRES = "Thu, 03 Dec 2026 19:36:03 GMT"
MFA_EXPIRES_TS = datetime(2026, 12, 3, 19, 36, 3, tzinfo=UTC).timestamp()


class FakePortal:
    """Portal whose refresh() must not be needed while the session works."""

    def __init__(self, dead: bool = False) -> None:
        self.refreshes = 0
        self.dead = dead

    async def refresh(self) -> None:
        self.refreshes += 1

    def session_summary(self) -> str:
        return "MFA cookie until unknown"

    async def _answer(self, payload: dict) -> dict:
        if self.dead:
            raise wp.WebsitePortalAuthError("portal session rejected (HTTP 401)")
        return payload

    async def get_maintenance(self, vin: str) -> dict:
        return await self._answer({"mileage_km": 42000})

    async def get_charging(self, vin: str) -> dict:
        return await self._answer({"soc": 80})

    async def get_warning_lights(self, vin: str) -> dict:
        return await self._answer({"warning_lights": 0})

    async def get_lock_history(self, vin: str) -> dict:
        return await self._answer({})

    async def get_vehicle_images(self, vin: str) -> dict:
        return await self._answer({})

    async def get_vehicle_info(self, vin: str) -> dict:
        return await self._answer({})


class FakeCoordinator:
    """Just enough coordinator to drive _merge_portal unbound."""

    def __init__(self, portal: FakePortal) -> None:
        self.portal = portal
        self.portal_keys = co.defaultdict(set)

    _portal_fetch = co.VolkswagenConnectCoordinator._portal_fetch
    _merge_one = co.VolkswagenConnectCoordinator._merge_one
    _merge_portal = co.VolkswagenConnectCoordinator._merge_portal

    def _persist_portal_cookies(self) -> None:
        pass


def _merge(portal: FakePortal) -> None:
    result = {VIN: co.VehicleData(vin=VIN, info={"vin": VIN})}
    asyncio.run(FakeCoordinator(portal)._merge_portal(result))


def test_poll_does_not_renew_on_its_own() -> None:
    portal = FakePortal()
    _merge(portal)
    assert portal.refreshes == 0, portal.refreshes


def test_dead_session_reaches_reauth_and_logs_the_expiries() -> None:
    log = TestCase()
    with log.assertLogs(co._LOGGER, "INFO") as captured:
        try:
            _merge(FakePortal(dead=True))
        except ConfigEntryAuthFailed:
            pass
        else:
            raise AssertionError("dead portal session was swallowed")
    text = "\n".join(captured.output)
    assert "Portal session ended" in text and "MFA cookie until unknown" in text, text


def _identity_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        headers=[
            ("set-cookie", "auth0-mfa-v2=m; Max-Age=604800; Path=/; Secure"),
            ("set-cookie", f"auth0=a; Path=/; Expires={MFA_EXPIRES}; Secure"),
            ("set-cookie", "idkit_uid=u; Path=/; Secure"),
        ],
    )


async def _logged_in_client() -> tuple[wp.WebsitePortalClient, Http2Session]:
    session = Http2Session(httpx.AsyncClient(transport=httpx.MockTransport(_identity_handler)))
    client = wp.WebsitePortalClient(session, "a@b.c", "pw")
    async with session.get(f"{IDENTITY}/u/login") as response:
        assert response.status == 200
    return client, session


def test_session_records_the_expiry_vw_asks_for() -> None:
    async def run() -> None:
        with patch("time.time", return_value=NOW):
            _, session = await _logged_in_client()
        assert session.cookie_expiry == {
            ("identity.vwgroup.io", "auth0-mfa-v2"): NOW + 604800,
            ("identity.vwgroup.io", "auth0"): MFA_EXPIRES_TS,
        }, session.cookie_expiry

    asyncio.run(run())


def test_expiry_survives_export_and_import() -> None:
    async def run() -> None:
        with patch("time.time", return_value=NOW):
            client, _ = await _logged_in_client()
            exported = {(c["key"]): c for c in client.export_cookies()}
            assert exported["auth0-mfa-v2"]["expires"] == int(NOW + 604800), exported
            assert "expires" not in exported["idkit_uid"], exported
            restored = wp.WebsitePortalClient(
                Http2Session(httpx.AsyncClient()), "a@b.c", "pw"
            )
            restored.import_cookies(list(exported.values()))
            summary = restored.session_summary()
        assert "MFA cookie until 1970-01-19 13:46 UTC" in summary, summary
        assert "SSO cookie until 2026-12-03 19:36 UTC" in summary, summary
        assert "portal cookie until unknown" in summary, summary

    asyncio.run(run())


def _refreshing_client(mfa_expiry: float | None) -> tuple[wp.WebsitePortalClient, list[str]]:
    session = Http2Session(httpx.AsyncClient())
    if mfa_expiry is not None:
        session.cookie_expiry[("identity.vwgroup.io", "auth0-mfa-v2")] = mfa_expiry
    client = wp.WebsitePortalClient(session, "a@b.c", "pw")
    visits: list[str] = []

    async def silent() -> None:
        visits.append("authorize")

    client._silent_refresh = silent
    return client, visits


def test_lapsed_mfa_cookie_never_visits_vw() -> None:
    """Authorize mails a code once the cookie is gone; that mail belongs to the user's reauth."""

    async def run() -> None:
        with patch("time.time", return_value=NOW):
            client, visits = _refreshing_client(NOW - 1)
            for _ in range(2):
                try:
                    await client.refresh()
                except wp.WebsitePortalOtpRequired:
                    pass
                else:
                    raise AssertionError("expected an email code request")
        assert visits == [], visits

    asyncio.run(run())


def test_valid_or_unknown_mfa_cookie_refreshes_as_before() -> None:
    async def run() -> None:
        with patch("time.time", return_value=NOW):
            for expiry in (NOW + 60, None):
                client, visits = _refreshing_client(expiry)
                await client.refresh()
                assert visits == ["authorize"], (expiry, visits)

    asyncio.run(run())


def _portal_client(
    statuses: list[int], mfa_expiry: float | None
) -> tuple[wp.WebsitePortalClient, list[str]]:
    """Client whose data calls answer ``statuses`` in turn; the list records authorize visits."""
    answers = iter(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(answers)
        return httpx.Response(status, text="<html>" if status >= 500 else "{}")

    session = Http2Session(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    if mfa_expiry is not None:
        session.cookie_expiry[("identity.vwgroup.io", "auth0-mfa-v2")] = mfa_expiry
    client = wp.WebsitePortalClient(session, "a@b.c", "pw")
    visits: list[str] = []

    async def silent() -> None:
        visits.append("authorize")

    client._silent_refresh = silent
    return client, visits


async def _outcome(client: wp.WebsitePortalClient) -> str:
    try:
        status, _ = await client._get("/x")
    except wp.WebsitePortalOtpRequired:
        return "code"
    except wp.WebsitePortalVehicleError:
        return "skipped"
    return f"ok {status}"


def test_working_session_is_not_renewed() -> None:
    async def run() -> None:
        client, visits = _portal_client([200], NOW - 1)
        assert await _outcome(client) == "ok 200"
        assert visits == [], visits

    asyncio.run(run())


def test_stale_session_is_renewed_once() -> None:
    async def run() -> None:
        with patch("time.time", return_value=NOW):
            client, visits = _portal_client([412, 200], NOW + 60)
            assert await _outcome(client) == "ok 200"
        assert visits == ["authorize"], visits

    asyncio.run(run())


def test_lapsed_mfa_ends_the_session_only_on_a_clear_signal() -> None:
    """A refusal or outage on one endpoint must not put a working session into reauth."""

    async def run() -> None:
        with patch("time.time", return_value=NOW):
            for status, expected in (
                (401, "code"), (412, "code"), (403, "skipped"), (428, "skipped"), (502, "skipped"),
            ):
                client, visits = _portal_client([status], NOW - 1)
                assert await _outcome(client) == expected, status
                assert visits == [], (status, visits)

    asyncio.run(run())


def test_lapsed_mfa_cookie_is_remembered_across_a_restart() -> None:
    """The jar drops an expired cookie, so its expiry has to be stored without it."""

    async def run() -> None:
        with patch("time.time", return_value=NOW):
            before, _ = _portal_client([], NOW - 1)
            stored = before.export_cookies()
            assert stored == [
                {"domain": "identity.vwgroup.io", "key": "auth0-mfa-v2", "value": "", "expires": int(NOW - 1)}
            ], stored
            after, visits = _portal_client([], None)
            after.import_cookies(stored)
            try:
                await after.refresh()
            except wp.WebsitePortalOtpRequired:
                pass
            else:
                raise AssertionError("expected an email code request")
        assert visits == [], visits
        assert list(after._session.cookie_jar) == []

    asyncio.run(run())


def test_old_entry_without_expiry_still_imports() -> None:
    async def run() -> None:
        client = wp.WebsitePortalClient(Http2Session(httpx.AsyncClient()), "a@b.c", "pw")
        client.import_cookies([{"domain": "identity.vwgroup.io", "key": "auth0", "value": "a"}])
        assert client.session_summary().startswith("MFA cookie until unknown"), client.session_summary()

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall checks passed")
