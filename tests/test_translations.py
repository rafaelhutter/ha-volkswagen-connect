"""Self-check: every translated entity has an English name, and no language has orphans.

A translation_key without a strings.json entry leaves the entity nameless.
Run inside the HA container (needs homeassistant): python3 tests/test_translations.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.volkswagen_connect.binary_sensor import BINARY_KEYS  # noqa: E402
from custom_components.volkswagen_connect.const import translation_key  # noqa: E402
from custom_components.volkswagen_connect.image import TRANSLATED_VIEWS  # noqa: E402
from custom_components.volkswagen_connect.sensor import KNOWN_KEYS  # noqa: E402

COMPONENT = ROOT / "custom_components/volkswagen_connect"
# hassfest's rule: lowercase, no leading/trailing/doubled separators.
VALID_KEY = re.compile(r"^(?!.+[_-]{2})(?![_-])[a-z0-9-_]+(?<![_-])$")


def _expected() -> dict[str, set[str]]:
    expected = {"sensor": {"data_status", "data_captured"}, "binary_sensor": set()}
    for platform, keys in (("sensor", KNOWN_KEYS), ("binary_sensor", BINARY_KEYS)):
        slugs = [translation_key(k) for k in keys]
        assert len(slugs) == len(set(slugs)), f"{platform}: two keys share a translation key"
        expected[platform] |= set(slugs)
    expected["image"] = {"image"} | {f"image_view_{v}" for v in TRANSLATED_VIEWS}
    return expected


def _names(path: pathlib.Path) -> dict[str, set[str]]:
    entity = json.loads(path.read_text())["entity"]
    for platform, keys in entity.items():
        for key, value in keys.items():
            assert value.get("name"), f"{path.name}: {platform}.{key} has no name"
    return {platform: set(keys) for platform, keys in entity.items()}


def main() -> None:
    expected = _expected()
    for keys in expected.values():
        for key in keys:
            assert VALID_KEY.match(key), f"invalid translation key {key!r}"
    strings = json.loads((COMPONENT / "strings.json").read_text())
    assert strings == json.loads((COMPONENT / "translations/en.json").read_text()), "en.json != strings.json"
    assert _names(COMPONENT / "strings.json") == expected, "strings.json: entity keys differ from the code"
    # A missing name falls back to English; an extra one is an orphan.
    for path in sorted((COMPONENT / "translations").glob("*.json")):
        for platform, keys in _names(path).items():
            orphans = keys - expected.get(platform, set())
            assert not orphans, f"{path.name}: {platform} keys unknown to the code: {orphans}"
    print("all checks passed")


main()
