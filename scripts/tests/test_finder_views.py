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

from ds_store import DSStore

if TYPE_CHECKING:
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
ICON_VIEW = (b"type", b"icnv")


def write_store(path: Path, records: dict[str, dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with DSStore.open(str(path), "w+") as store:
        for filename, codes in records.items():
            for code, value in codes.items():
                store[filename][code] = value


def read_store(path: Path) -> dict[tuple[str, bytes], object]:
    with DSStore.open(str(path), "r") as store:
        return {(entry.filename, entry.code): entry.value for entry in store}


def run(home: Path) -> MagicMock:
    defaults = MagicMock(stdout=plistlib.dumps(PREFERENCES))
    with (
        patch.object(finder_views_module.Path, "home", return_value=home),
        patch.object(finder_views_module.subprocess, "run", return_value=defaults) as run,
    ):
        finder_views_module.main()
    return run


def killed_finder(run: MagicMock) -> bool:
    return any(call.args[0][0] == "/usr/bin/killall" for call in run.call_args_list)


def test_resets_folder_views_and_pins_downloads_to_the_trash_view(tmp_path: Path) -> None:
    write_store(tmp_path / ".DS_Store", {"Downloads": {"vstl": ICON_VIEW}})
    write_store(
        tmp_path / "Documents" / ".DS_Store",
        {"Projects": {"vstl": ICON_VIEW, "lsvp": {"sortColumn": "kind"}, "Iloc": (16, 32)}},
    )
    # Finder doesn't browse hidden folders or Library, so they're left alone
    hidden = tmp_path / ".config" / ".DS_Store"
    write_store(hidden, {"thing": {"vstl": ICON_VIEW}})

    assert killed_finder(run(tmp_path))

    home = read_store(tmp_path / ".DS_Store")
    assert home["Downloads", b"vstl"] == b"Nlsv"
    assert home["Downloads", b"lsvp"] == TRASH_LIST_VIEW
    extended = home["Downloads", b"lsvC"]
    assert isinstance(extended, bytearray)
    assert plistlib.loads(bytes(extended)) == TRASH_EXTENDED_LIST_VIEW
    # Only the view is reset; icon positions stay
    assert read_store(tmp_path / "Documents" / ".DS_Store") == {("Projects", b"Iloc"): (16, 32)}
    assert read_store(hidden) == {("thing", b"vstl"): b"icnv"}


def test_leaves_finder_alone_when_every_view_is_already_set(tmp_path: Path) -> None:
    write_store(tmp_path / "Documents" / ".DS_Store", {"Projects": {"vstl": ICON_VIEW}})
    run(tmp_path)

    # Finder rewrites scroll positions as you browse, which isn't a view change
    with DSStore.open(str(tmp_path / ".DS_Store"), "r+") as store:
        store["Downloads"]["lsvp"] = {**TRASH_LIST_VIEW, "scrollPositionY": 120.0}

    assert not killed_finder(run(tmp_path))
