"""Self-check: a battery-only car loses VW's meaningless fuel fields, a plug-in hybrid keeps them (#33).

Run inside the HA container (needs the integration's deps): python3 tests/test_battery_only_fuel.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from custom_components.volkswagen_connect import coordinator as co  # noqa: E402

# Shapes of real flat payloads: #33 (e-up!), TommiG1/HA_VAG-EU-Data-Act#13 (e-Golf),
# mikrohard/CarConnectivity-connector-vw-eu-data-act#5 (Passat PHEV).
E_UP = {"state_of_charge": 70, "fuel_level_current_level": 100, "fuel_level__accuracy": 0}
E_GOLF = {"state_of_charge": 56, "fuel_level_current_level": None, "cruising_range_secondary_engine": None}
PHEV = {"state_of_charge": 80, "fuel_level_current_level": 17, "cruising_range_secondary_engine": 93}
PETROL = {"fuel_level_current_level": 55, "cruising_range_primary_engine": 610}


def delivered(values: dict, traits: set[str] | None = None) -> dict:
    values = dict(values)
    co._drop_fuel_of_battery_only(values, set() if traits is None else traits)
    return values


def test_battery_only_cars_lose_the_fuel_fields() -> None:
    for car in (E_UP, E_GOLF):
        left = delivered(car)
        assert "fuel_level_current_level" not in left and "fuel_level__accuracy" not in left, left
        assert left["state_of_charge"] == car["state_of_charge"], left


def test_hybrid_and_petrol_keep_their_fuel_level() -> None:
    assert delivered(PHEV)["fuel_level_current_level"] == 17
    assert delivered(PETROL)["fuel_level_current_level"] == 55


def test_a_thin_delivery_does_not_bring_the_fuel_level_back() -> None:
    traits: set[str] = set()
    delivered(E_UP, traits)
    assert delivered({"fuel_level_current_level": 100}, traits) == {}


def test_a_hybrid_with_an_empty_electric_range_stays_a_hybrid() -> None:
    traits: set[str] = set()
    delivered(PHEV, traits)
    empty = {**PHEV, "cruising_range_secondary_engine": None}
    assert delivered(empty, traits)["fuel_level_current_level"] == 17


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall checks passed")
