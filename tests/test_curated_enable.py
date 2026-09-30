"""Self-check: a field created disabled while uncurated comes back on once curated (#33).

Run inside the HA container (needs homeassistant): python3 tests/test_curated_enable.py
"""

from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from homeassistant.helpers.entity_registry import RegistryEntryDisabler  # noqa: E402

from custom_components.volkswagen_connect import sensor  # noqa: E402


class _Registry:
    """One registry entry for every unique id, disabled by ``disabled_by``."""

    def __init__(self, disabled_by: RegistryEntryDisabler | None) -> None:
        self.entry = SimpleNamespace(disabled_by=disabled_by)
        self.updates: list[tuple[str, dict]] = []

    def async_get_entity_id(self, domain: str, platform: str, unique_id: str) -> str:
        return f"{domain}.{unique_id.lower()}"

    def async_get(self, entity_id: str):
        return self.entry

    def async_update_entity(self, entity_id: str, **changes) -> None:
        self.updates.append((entity_id, changes))


def test_curated_field_disabled_by_the_integration_comes_back() -> None:
    registry = _Registry(RegistryEntryDisabler.INTEGRATION)
    sensor._enable_if_curated(registry, "VIN", "state_of_charge")
    assert registry.updates == [("sensor.vin_state_of_charge", {"disabled_by": None})], registry.updates


def test_user_choice_and_raw_fields_stay_off() -> None:
    by_user = _Registry(RegistryEntryDisabler.USER)
    sensor._enable_if_curated(by_user, "VIN", "state_of_charge")
    raw = _Registry(RegistryEntryDisabler.INTEGRATION)
    sensor._enable_if_curated(raw, "VIN", "some_raw_code")
    assert by_user.updates == [] and raw.updates == [], (by_user.updates, raw.updates)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall checks passed")
