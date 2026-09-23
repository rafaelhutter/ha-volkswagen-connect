"""Self-check: _gdc_for resolves the cluster and logs relation diagnostics (#30).

Needs the integration's deps, so run it inside the HA container:
    python3 tests/test_gdc_relation_log.py
"""

from __future__ import annotations

import asyncio
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from custom_components.volkswagen_connect import website_portal as wp  # noqa: E402

VIN = "WVWZZZ00000000001"


class FakePortal:
    """Drives WebsitePortalClient._gdc_for with a canned relations response."""

    _gdc_for = wp.WebsitePortalClient._gdc_for
    # Re-wrap: reading a staticmethod off the class yields a plain function.
    _log_relation = staticmethod(wp.WebsitePortalClient._log_relation)

    def __init__(self, status: int, body: str) -> None:
        self._gdc_cache: dict[str, str] = {}
        self._status, self._body = status, body

    async def _get(self, path: str, *a, **k):
        return self._status, self._body


def _resolve(status: int, body: str) -> tuple[str, list[str]]:
    portal = FakePortal(status, body)
    lines: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())

    wp._LOGGER.addHandler(_Capture())
    wp._LOGGER.setLevel(logging.DEBUG)
    try:
        gdc = asyncio.run(portal._gdc_for(VIN))
    finally:
        wp._LOGGER.handlers = [h for h in wp._LOGGER.handlers if not isinstance(h, _Capture)]
    return gdc, lines


def test_mbb_car_resolves_to_mbb_and_logs_role() -> None:
    body = '{"relation": {"role": "PRIMARY_USER", "enrollmentStatus": "COMPLETED", "vehicle": {"modBackend": "MBB_ODP"}}}'
    gdc, lines = _resolve(200, body)
    assert gdc == "mbb", gdc
    assert any("role=PRIMARY_USER" in ln and "enrollment=COMPLETED" in ln for ln in lines), lines


def test_id_car_defaults_to_wcar() -> None:
    body = '{"relation": {"vehicle": {"modBackend": "WCAR"}}}'
    gdc, _ = _resolve(200, body)
    assert gdc == "wcar", gdc


def test_unlinked_vin_logs_the_not_linked_hint() -> None:
    """The #30 case: relation lookup fails -> keep default, name the likely cause."""
    gdc, lines = _resolve(404, "")
    assert gdc == "wcar", gdc
    assert any("may not be linked to this account" in ln for ln in lines), lines


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall checks passed")
