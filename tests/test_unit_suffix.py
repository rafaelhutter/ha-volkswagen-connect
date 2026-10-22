"""Self-check: "<number> Unit_<code>" values read as numbers with a unit (#44).

Needs homeassistant, so run it inside the HA container:
    python3 tests/test_unit_suffix.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from custom_components.volkswagen_connect.sensor import _split_unit  # noqa: E402


def main() -> None:
    assert _split_unit("17.0 Unit_DegreCelsi") == (17.0, "°C")
    assert _split_unit(" 339.75 Unit_Volt ") == (339.75, "V")
    assert _split_unit("-0.8 Unit_Amper") == (-0.8, "A")
    # An unmapped code still graphs; its name stands in for the unit.
    assert _split_unit("86 Unit_Perce") == (86.0, "Perce")
    for other in ("17.0", "Unit_Volt", "about 3 Unit_Volt", "CHARGE_STATE_OFF", 17, None):
        assert _split_unit(other) is None, other
    print("ok")


if __name__ == "__main__":
    main()
