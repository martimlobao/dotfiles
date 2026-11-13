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

import importlib.util
import plistlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from ds_store import DSStore, DSStoreEntry

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import ModuleType

SPEC = importlib.util.spec_from_file_location(
    "finder_views_module", Path("scripts/finder_views.py")
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("failed to load scripts/finder_views.py")
finder_views = importlib.util.module_from_spec(SPEC)
sys.modules["finder_views_module"] = finder_views
SPEC.loader.exec_module(finder_views)
finder_views_module: ModuleType = finder_views

TRASH_LIST_VIEW = {"sortColumn": "dateAdded", "columns": {"dateAdded": {"visible": True}}}
TRASH_EXTENDED_LIST_VIEW = {
    "sortColumn": "dateAdded",
    "columns": [{"identifier": "dateAdded", "visible": True}],
}
PREFERENCES = {
    "TrashViewSettings": {
        "ListViewSettings": TRASH_LIST_VIEW,
        "ExtendedListViewSettingsV2": TRASH_EXTENDED_LIST_VIEW,
    }
}


def entry(filename: str, code: bytes, value: bytes) -> DSStoreEntry:
    return DSStoreEntry(filename, code, b"type" if len(value) == 4 else b"blob", value)


def plist(value: Mapping[str, object]) -> bytes:
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY)


def write_store(path: Path, entries: list[DSStoreEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with DSStore.open(str(path), "w+") as store:
        for item in entries:
            store.insert(item)


def read_store(path: Path) -> dict[tuple[str, bytes], bytes]:
    with DSStore.open(str(path), "r") as store:
        return {(item.filename, item.code): bytes(item.value) for item in store}


def run(home: Path) -> MagicMock:
    def command(args: list[str], **_: object) -> MagicMock:
        if args[0] == "/usr/bin/defaults":
            return MagicMock(stdout=plistlib.dumps(PREFERENCES))
        return MagicMock(stdout="")

    with (
        patch.object(finder_views_module.Path, "home", return_value=home),
        patch.object(finder_views_module.subprocess, "run", side_effect=command) as run,
    ):
        finder_views_module.main()
    return run


def killed_finder(run: MagicMock) -> bool:
    return any(call.args[0][0] == "/usr/bin/killall" for call in run.call_args_list)


def test_resets_home_views_and_pins_downloads_to_the_trash_view(tmp_path: Path) -> None:
    write_store(
        tmp_path / ".DS_Store",
        [
            entry(".", b"vstl", b"icnv"),
            entry("Documents", b"vstl", b"icnv"),
            entry("Downloads", b"vstl", b"icnv"),
        ],
    )
    # Views saved deeper down are out of scope
    nested = tmp_path / "Documents" / ".DS_Store"
    write_store(nested, [entry("Projects", b"vstl", b"icnv")])

    assert killed_finder(run(tmp_path))

    home = read_store(tmp_path / ".DS_Store")
    assert home.keys() == {("Downloads", b"vstl"), ("Downloads", b"lsvp"), ("Downloads", b"lsvC")}
    assert home["Downloads", b"vstl"] == b"Nlsv"
    assert plistlib.loads(home["Downloads", b"lsvp"]) == TRASH_LIST_VIEW
    assert plistlib.loads(home["Downloads", b"lsvC"]) == TRASH_EXTENDED_LIST_VIEW
    assert read_store(nested) == {("Projects", b"vstl"): b"icnv"}


def test_leaves_finder_alone_when_only_downloads_is_pinned(tmp_path: Path) -> None:
    # Finder adds its own records and rewrites scroll positions as you browse
    write_store(
        tmp_path / ".DS_Store",
        [
            entry("Downloads", b"vstl", b"Nlsv"),
            entry("Downloads", b"lsvp", plist({**TRASH_LIST_VIEW, "scrollPositionY": 120.0})),
            entry("Downloads", b"lsvC", plist(TRASH_EXTENDED_LIST_VIEW)),
            entry("Documents", b"bwsp", plist({"ShowSidebar": True})),
        ],
    )

    assert not killed_finder(run(tmp_path))
