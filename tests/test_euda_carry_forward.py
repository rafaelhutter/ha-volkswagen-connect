"""Self-check: a partial EU Data Act delivery must not blank the fields it left out.

Run inside the HA container (needs the integration's deps): python3 tests/test_euda_carry_forward.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from custom_components.volkswagen_connect import coordinator as co  # noqa: E402

# Shapes of real ID.7 deliveries 15 min apart: the second one lacks "locked".
FULL = {"locked": "true", "outdoor_temperature": 13.5, "battery_state_report.soc": 70}
PARTIAL = {"outdoor_temperature": 9.0}


def test_a_partial_delivery_keeps_the_missing_fields() -> None:
    known: dict = {}
    co._carry_forward(known, FULL)
    values = co._carry_forward(known, PARTIAL)
    assert values["locked"] == "true", values
    assert values["outdoor_temperature"] == 9.0, values


def test_dropping_a_field_from_the_result_keeps_it_known() -> None:
    known: dict = {}
    co._carry_forward(known, FULL).pop("locked")
    assert co._carry_forward(known, PARTIAL)["locked"] == "true"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall checks passed")
