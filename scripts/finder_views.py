#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "ds-store>=1.3.2,<2.0.0",
# ]
# [tool.uv]
# exclude-newer = "2026-02-12T00:00:00Z"
# ///

"""Make the home folder and the folders in it use Finder's default views.

Finder saves a folder's view in its parent's .DS_Store as soon as the view
is changed, and that overrides the defaults macos.sh sets. The views of the
home folder (stored as ".") and of every folder in it live in ~/.DS_Store, so
whenever it holds a saved view, replace it with one that only pins Downloads
to the Trash's view (the default list view sorted by date added).

The rest of ~/.DS_Store is a cache Finder rebuilds (icon positions, window
sizes, expanded rows), so it isn't kept: ds_store can't reliably rewrite a
store that size, but it can write a small one from scratch.
"""

from __future__ import annotations

import os
import plistlib
import subprocess  # noqa: S404
import time
from dataclasses import dataclass
from pathlib import Path

from ds_store import DSStore, DSStoreEntry
from ds_store import store as ds_store_module

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
# Finder rewrites these as you scroll, so they aren't part of the view
SCROLL_KEYS = frozenset({"scrollPositionX", "scrollPositionY"})
LIST_VIEW = b"Nlsv"
FINDER_QUIT_TIMEOUT_SECONDS = 10

# Read every record as raw bytes, so views are compared as the plists Finder
# wrote rather than through ds_store's decoders
ds_store_module.codecs.clear()


@dataclass(frozen=True)
class PinnedView:
    """The view records a folder must have in its parent's .DS_Store."""

    folder: str
    # ListViewSettings and ExtendedListViewSettingsV2, without scroll positions
    list_view: dict[str, object]
    extended_list_view: dict[str, object]

    def entries(self) -> list[DSStoreEntry]:
        def plist(view: dict[str, object]) -> bytes:
            return plistlib.dumps(view, fmt=plistlib.FMT_BINARY)

        return [
            DSStoreEntry(self.folder, b"vstl", b"type", LIST_VIEW),
            DSStoreEntry(self.folder, b"lsvp", b"blob", plist(self.list_view)),
            DSStoreEntry(self.folder, b"lsvC", b"blob", plist(self.extended_list_view)),
        ]

    def matches(self, entry: DSStoreEntry) -> bool:
        if entry.filename != self.folder:
            return False
        if entry.code == b"vstl":
            return entry.value == LIST_VIEW
        view = {b"lsvp": self.list_view, b"lsvC": self.extended_list_view}.get(entry.code)
        value = entry.value
        if view is None or not isinstance(value, (bytes, bytearray)):
            return False
        return without_scroll(plistlib.loads(bytes(value))) == view


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


def is_enforced(path: Path, pinned: PinnedView) -> bool:
    # Whether the store's only saved views are the pinned ones
    if not path.exists():
        return False
    try:
        with DSStore.open(str(path), "r") as store:
            views = [entry for entry in store if entry.code in VIEW_CODES]
        # Each code appears once per folder, so this is exactly the pinned ones
        return len(views) == len(pinned.entries()) and all(map(pinned.matches, views))
    except Exception as error:  # noqa: BLE001 - a corrupt store is replaced like a stale one
        print(f"⚠️  \033[1;33mReplacing unreadable {path}: {error}\033[0m")
        return False


def write_store(path: Path, entries: list[DSStoreEntry]) -> None:
    # Build the new file next to the old one and swap it in, so a failed
    # write never leaves a half-written .DS_Store behind
    staging = path.with_name(".DS_Store.finder_views")
    with DSStore.open(str(staging), "w+") as store:
        for entry in entries:
            store.insert(entry)
    staging.replace(path)


def quit_finder() -> None:
    """Quits Finder and waits for it to exit; launchd relaunches it."""
    pids = subprocess.run(
        ["/usr/bin/pgrep", "-x", "Finder"], check=False, capture_output=True, text=True
    ).stdout.split()
    subprocess.run(["/usr/bin/killall", "Finder"], check=False, capture_output=True)
    deadline = time.monotonic() + FINDER_QUIT_TIMEOUT_SECONDS
    for pid in map(int, pids):
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)


def main() -> None:
    pinned = downloads_view(finder_preferences())
    path = Path.home() / ".DS_Store"
    if is_enforced(path, pinned):
        print("✅ \033[1;32mAlready set: home folders use the default Finder views\033[0m")
        return
    # Finder writes the views of open windows back to their .DS_Store when it
    # quits, so let it finish quitting before replacing the file
    quit_finder()
    write_store(path, pinned.entries())
    print("🔧 \033[1;33mUpdated: home folders use the default Finder views\033[0m")
    print("🔧 \033[1;33mUpdated: Downloads uses the Trash's view\033[0m")


if __name__ == "__main__":
    main()
