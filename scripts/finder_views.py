#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "ds-store>=1.3.3,<2.0.0",
# ]
# [tool.uv]
# exclude-newer = "2026-02-12T00:00:00Z"
# ///

"""Make every folder under the home folder use Finder's default views.

Finder saves a folder's view in its parent's .DS_Store as soon as the view
is changed, and that overrides the defaults macos.sh sets. Strip those
records so every folder falls back to the defaults, except Downloads, which
gets the Trash's view (the default list view sorted by date added). Other
records, such as icon positions and window sizes, are left alone.
"""

from __future__ import annotations

import os
import plistlib
import subprocess  # noqa: S404
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ds_store import DSStore, DSStoreEntry

if TYPE_CHECKING:
    from collections.abc import Iterator

# Records holding a folder's view style and the options of each view
VIEW_CODES = frozenset({
    b"vstl",
    b"lsvp",
    b"lsvP",
    b"lsvC",
    b"lsvo",
    b"lsvt",
    b"icvp",
    b"icvo",
    b"icvt",
    b"glvp",
})
# Finder doesn't browse these, and walking them is slow
SKIPPED_DIRS = frozenset({"Library", "node_modules"})
# Finder rewrites these as you scroll, so they aren't part of the view
SCROLL_KEYS = frozenset({"scrollPositionX", "scrollPositionY"})
LIST_VIEW = b"Nlsv"


@dataclass(frozen=True)
class PinnedView:
    """The view records a folder must have in its parent's .DS_Store."""

    folder: str
    # ListViewSettings, decoded by ds_store's plist codec
    list_view: dict[str, object]
    # ExtendedListViewSettingsV2, which ds_store keeps as a raw binary plist
    extended_list_view: dict[str, object]


def without_scroll(view: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in view.items() if key not in SCROLL_KEYS}


def finder_preferences() -> dict[str, object]:
    exported: bytes = subprocess.run(
        ["/usr/bin/defaults", "export", "com.apple.finder", "-"], check=True, capture_output=True
    ).stdout
    return plistlib.loads(exported)


def downloads_view(preferences: dict[str, object]) -> PinnedView:
    trash = preferences.get("TrashViewSettings")
    if not isinstance(trash, dict):
        raise SystemExit("❌ TrashViewSettings is missing; run macos.sh to set the Trash's view")
    return PinnedView(
        folder="Downloads",
        list_view=without_scroll(trash["ListViewSettings"]),
        extended_list_view=without_scroll(trash["ExtendedListViewSettingsV2"]),
    )


def ds_stores(home: Path) -> Iterator[Path]:
    for directory, subdirectories, files in os.walk(home):
        # Skip hidden folders (including the Trash) and app bundles, which
        # Finder doesn't browse
        subdirectories[:] = [
            name
            for name in subdirectories
            if not name.startswith(".") and not name.endswith(".app") and name not in SKIPPED_DIRS
        ]
        if ".DS_Store" in files:
            yield Path(directory) / ".DS_Store"


def stale_records(path: Path, pinned: PinnedView | None) -> list[tuple[str, bytes]]:
    """Returns a .DS_Store's view records to delete, keeping pinned ones."""
    with DSStore.open(str(path), "r") as store:
        return [
            (entry.filename, entry.code)
            for entry in store
            if entry.code in VIEW_CODES
            and not (pinned and entry.filename == pinned.folder and is_pinned(entry, pinned))
        ]


def is_pinned(entry: DSStoreEntry, pinned: PinnedView) -> bool:
    value: object = entry.value
    if entry.code == b"vstl":
        return value == LIST_VIEW
    if entry.code == b"lsvp" and isinstance(value, dict):
        return without_scroll(value) == pinned.list_view
    if entry.code == b"lsvC" and isinstance(value, (bytes, bytearray)):
        return without_scroll(plistlib.loads(bytes(value))) == pinned.extended_list_view
    return False


def missing_pinned_records(path: Path, pinned: PinnedView) -> bool:
    if not path.exists():
        return True
    with DSStore.open(str(path), "r") as store:
        codes = {entry.code for entry in store[pinned.folder] if is_pinned(entry, pinned)}
    return codes != {b"vstl", b"lsvp", b"lsvC"}


def write_pinned(path: Path, pinned: PinnedView) -> None:
    with DSStore.open(str(path), "r+" if path.exists() else "w+") as store:
        records = store[pinned.folder]
        records["vstl"] = (b"type", LIST_VIEW)
        records["lsvp"] = pinned.list_view
        records["lsvC"] = (
            b"blob",
            plistlib.dumps(pinned.extended_list_view, fmt=plistlib.FMT_BINARY),
        )


def delete_records(path: Path, records: list[tuple[str, bytes]]) -> None:
    with DSStore.open(str(path), "r+") as store:
        for filename, code in records:
            store.delete(filename, code)


def main() -> None:
    home = Path.home()
    pinned = downloads_view(finder_preferences())
    pinned_store = home / ".DS_Store"

    stale: dict[Path, list[tuple[str, bytes]]] = {}
    for path in ds_stores(home):
        try:
            records = stale_records(path, pinned if path == pinned_store else None)
        except Exception as error:  # noqa: BLE001 - a corrupt .DS_Store shouldn't stop the rest
            print(f"⚠️  \033[1;33mSkipping unreadable {path}: {error}\033[0m")
            continue
        if records:
            stale[path] = records
    repin = missing_pinned_records(pinned_store, pinned)

    if not stale and not repin:
        print("✅ \033[1;32mAlready set: every folder uses the default Finder views\033[0m")
        return
    # Finder writes the views of open windows back to their .DS_Store when it
    # quits, so quit it before editing; it relaunches on its own
    subprocess.run(["/usr/bin/killall", "Finder"], check=False, capture_output=True)
    for path, records in stale.items():
        delete_records(path, records)
    if repin:
        write_pinned(pinned_store, pinned)
        print("🔧 \033[1;33mUpdated: Downloads uses the Trash's view\033[0m")
    if stale:
        folders = sum(len({filename for filename, _ in records}) for records in stale.values())
        print(f"🔧 \033[1;33mUpdated: reset {folders} folders to the default Finder views\033[0m")


if __name__ == "__main__":
    main()
