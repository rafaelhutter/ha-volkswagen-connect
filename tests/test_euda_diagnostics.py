"""Self-check: base64 UDS diagnostic values unpack into their readings (#44).

    python3 tests/test_euda_diagnostics.py
"""

from __future__ import annotations

import base64
import importlib.util
import json
import pathlib
import sys
import types

# Stub the two third-party imports and load the module by path: the package
# __init__ pulls in homeassistant, which this check doesn't need.
for name in ("aiohttp", "bs4"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["bs4"].BeautifulSoup = object  # type: ignore[attr-defined]
_SRC = pathlib.Path(__file__).resolve().parents[1] / "custom_components/volkswagen_connect/eu_data_act.py"
_spec = importlib.util.spec_from_file_location("eu_data_act", _SRC)
eu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eu)

RANGE = "LL_GatewUDS_ReadDataByIdentMeasuValue_Calculated_value_range_display_0x2AB6"


def _blob(values: list[dict]) -> str:
    """A UDS diagnostic value as VW sends it: unpadded base64 of the JSON document."""
    doc = {"DiagnosticData": [{"DataObjects": [{"Values": values}]}]}
    return base64.b64encode(json.dumps(doc).encode()).decode().rstrip("=")


def _values(records: dict) -> dict:
    data = [{"key": f"k{i}", "dataFieldName": n, "value": v} for i, (n, v) in enumerate(records.items())]
    return eu._extract_values({"doc.json": {"Data": data}})[0]


def test_readings_replace_the_blob() -> None:
    blob = _blob([
        {"ParamShortName": "Param_RecorDataIdent", "Value": "2AB6"},
        {"ParamShortName": "Param_RangeSumDispl", "Value": "171"},
        {"ParamShortName": "Param_RangeUnitDispl", "Value": "kilometre"},
        {"ParamShortName": "Param_BatteVolta", "Value": 14.89},
        {"ParamShortName": "Param_Reserved_1", "Value": "0"},
        {"ParamShortName": "Param_LifeCycleData", "Value": "0" * 72},
    ])
    assert _values({RANGE: blob, "odometer": "1200"}) == {
        f"{RANGE}.RangeSumDispl": 171,
        f"{RANGE}.RangeUnitDispl": "kilometre",
        f"{RANGE}.BatteVolta": 14.89,
        "odometer": 1200,
    }


def test_a_value_that_does_not_decode_stays_as_it_is() -> None:
    assert _values({"note": "eyJ not base64 json"}) == {"note": "eyJ not base64 json"}


if __name__ == "__main__":
    test_readings_replace_the_blob()
    test_a_value_that_does_not_decode_stays_as_it_is()
    print("ok")
