# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "pytest>=9.0.2",
#     "pytest-cov>=7.0.0",
# ]
# [tool.uv]
# exclude-newer = "2026-02-12T00:00:00Z"
# ///
from __future__ import annotations

import argparse
import importlib.util
import plistlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from types import ModuleType

SPEC = importlib.util.spec_from_file_location("aerials_module", Path("scripts/aerials.py"))
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("failed to load scripts/aerials.py")
aerials = importlib.util.module_from_spec(SPEC)
sys.modules["aerials_module"] = aerials
SPEC.loader.exec_module(aerials)
aerials_module: ModuleType = aerials


def test_load_strings_supports_modern_loctable_bundle(tmp_path: Path) -> None:
    aerials_path = tmp_path / "aerials"
    bundle_path = (
        aerials_path
        / "manifest"
        / "TVIdleScreenStrings.bundle"
        / "Contents"
        / "Resources"
        / "Localizable.nocache.loctable"
    )
    bundle_path.parent.mkdir(parents=True)

    with bundle_path.open("wb") as fp:
        plistlib.dump(
            {
                "en": {"A007_C0001_NAME": "Sequoia Sunrise"},
                "pt": {"A007_C0001_NAME": "Nascer do sol em Sequoia"},
            },
            fp,
            fmt=plistlib.FMT_BINARY,
        )

    strings_path = aerials_module.resolve_strings_path(aerials_path)

    assert strings_path == bundle_path
    assert aerials_module.load_strings(strings_path) == {"A007_C0001_NAME": "Sequoia Sunrise"}


def test_load_strings_supports_legacy_strings_bundle(tmp_path: Path) -> None:
    aerials_path = tmp_path / "aerials"
    strings_path = (
        aerials_path
        / "manifest"
        / "TVIdleScreenStrings.bundle"
        / "en.lproj"
        / "Localizable.nocache.strings"
    )
    strings_path.parent.mkdir(parents=True)

    with strings_path.open("wb") as fp:
        plistlib.dump({"A007_C0001_NAME": "Sequoia Sunrise"}, fp)

    resolved_path = aerials_module.resolve_strings_path(aerials_path)

    assert resolved_path == strings_path
    assert aerials_module.load_strings(resolved_path) == {"A007_C0001_NAME": "Sequoia Sunrise"}


def test_resolve_strings_path_falls_back_to_legacy_location_when_missing(tmp_path: Path) -> None:
    expected_path = (
        tmp_path
        / "manifest"
        / "TVIdleScreenStrings.bundle"
        / "en.lproj"
        / "Localizable.nocache.strings"
    )

    assert aerials_module.resolve_strings_path(tmp_path) == expected_path


def test_parse_category_selection_all_returns_every_index() -> None:
    assert aerials_module.parse_category_selection("all", 3) == [1, 2, 3]
    assert aerials_module.parse_category_selection("4", 3) == [1, 2, 3]


def test_parse_category_selection_invalid_value_exits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        aerials_module.parse_category_selection("abc", 3)

    assert exc.value.code == 1
    assert "Invalid category selection" in capsys.readouterr().out


def test_parse_category_selection_out_of_range_exits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        aerials_module.parse_category_selection("0", 3)

    assert exc.value.code == 1
    assert "Invalid category selection: 0" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (
            argparse.Namespace(download=True, delete=False, list=False, open=False),
            ("d", "download"),
        ),
        (
            argparse.Namespace(download=False, delete=True, list=False, open=False),
            ("x", "delete"),
        ),
        (
            argparse.Namespace(download=False, delete=False, list=True, open=False),
            ("l", "list"),
        ),
        (argparse.Namespace(download=False, delete=False, list=False, open=True), ("o", "open")),
        (argparse.Namespace(download=False, delete=False, list=False, open=False), ("", "")),
    ],
)
def test_get_action_from_args_matches_flags(
    args: argparse.Namespace, expected: tuple[str, str]
) -> None:
    assert aerials_module.get_action_from_args(args) == expected


def test_select_localized_strings_falls_back_to_english() -> None:
    localizations = {
        "en": {"A007_C0001_NAME": "Sequoia Sunrise"},
        "pt": {"A007_C0001_NAME": "Nascer do sol em Sequoia"},
    }

    with patch.object(aerials_module.locale, "getlocale", return_value=("fr_FR", "UTF-8")):
        assert aerials_module.select_localized_strings(localizations) == {
            "A007_C0001_NAME": "Sequoia Sunrise"
        }


def test_select_localized_strings_returns_first_available_mapping() -> None:
    localizations = {
        "metadata": "ignored",
        "pt": {"A007_C0001_NAME": "Nascer do sol em Sequoia"},
    }

    with patch.object(aerials_module.locale, "getlocale", return_value=("fr_FR", "UTF-8")):
        assert aerials_module.select_localized_strings(localizations) == {
            "A007_C0001_NAME": "Nascer do sol em Sequoia"
        }


def test_select_localized_strings_returns_empty_for_non_mapping() -> None:
    assert aerials_module.select_localized_strings(["not", "a", "mapping"]) == {}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0 bytes"),
        (1, "1 byte"),
        (1024, "1.00 KB"),
    ],
)
def test_format_bytes_handles_small_values(value: int, expected: str) -> None:
    assert aerials_module.format_bytes(value) == expected


def test_format_name_truncates_long_names() -> None:
    assert aerials_module.format_name("A very long aerial name", length=10) == "A very ..."
    assert aerials_module.format_name("Short", length=10) == "Short     "


def test_save_cache_and_load_cache_round_trip(tmp_path: Path) -> None:
    cache_file = tmp_path / "nested" / "cache.json"
    cache = {"https://example.com/video.mov": {"length": 123, "timestamp": 456.0}}

    with patch.object(aerials_module, "CACHE_FILE", cache_file):
        aerials_module.save_cache(cache)
        assert aerials_module.load_cache() == cache


def test_load_cache_returns_empty_for_invalid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("{not valid json", encoding="utf-8")

    with patch.object(aerials_module, "CACHE_FILE", cache_file):
        assert aerials_module.load_cache() == {}

    output = capsys.readouterr().out
    assert "Error loading cache file" in output
    assert "Starting with fresh cache." in output


def test_clear_cache_removes_existing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("{}", encoding="utf-8")

    with patch.object(aerials_module, "CACHE_FILE", cache_file):
        aerials_module.clear_cache()

    assert not cache_file.exists()
    assert "Cache cleared." in capsys.readouterr().out


def test_clear_cache_reports_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache_file = tmp_path / "cache.json"

    with patch.object(aerials_module, "CACHE_FILE", cache_file):
        aerials_module.clear_cache()

    assert "Cache file not found" in capsys.readouterr().out
