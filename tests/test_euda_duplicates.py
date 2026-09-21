"""Self-check for the EU Data Act duplicate-dataFieldName rule (#29).

    python3 tests/test_euda_duplicates.py
"""

from __future__ import annotations

import importlib.util
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


def _dataset(records: list[dict]) -> dict:
    return {"doc.json": {"Data": records}}


def _rec(key: str, name: str, value, ts: str = "2026-09-20T10:00:00Z") -> dict:
    return {"key": key, "dataFieldName": name, "value": value, "timestampUtc": ts}


def test_lowest_key_wins_for_a_duplicated_name() -> None:
    """The #29 flip: one name under two keys must not depend on record order."""
    forwards = _dataset([_rec("aaa", "target_soc", 90), _rec("zzz", "target_soc", 80)])
    backwards = _dataset([_rec("zzz", "target_soc", 80), _rec("aaa", "target_soc", 90)])
    assert eu._extract_values(forwards)[0] == {"target_soc": 90}
    assert eu._extract_values(backwards)[0] == {"target_soc": 90}


def test_same_key_keeps_the_newest_sample() -> None:
    """Repeated samples of one signal still track the latest reading."""
    values, latest = eu._extract_values(
        _dataset(
            [
                _rec("aaa", "soc", 55, "2026-09-20T09:00:00Z"),
                _rec("aaa", "soc", 61, "2026-09-20T09:15:00Z"),
            ]
        )
    )
    assert values == {"soc": 61}, values
    assert latest == "2026-09-20T09:15:00Z", latest


def test_keyless_records_keep_the_last_value_as_before() -> None:
    records = [
        {"dataFieldName": "odometer", "value": 1},
        {"dataFieldName": "odometer", "value": 2},
    ]
    assert eu._extract_values(_dataset(records))[0] == {"odometer": 2}


def test_duplicate_across_two_files_in_one_delivery() -> None:
    raw = {"a.json": {"Data": [_rec("mmm", "range", 300)]},
           "b.json": {"Data": [_rec("bbb", "range", 250)]}}
    assert eu._extract_values(raw)[0] == {"range": 250}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall checks passed")
