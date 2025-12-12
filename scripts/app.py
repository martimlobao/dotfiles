#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "tomlkit>=0.13.2,<0.14",
# ]
# ///

"""Manage applications listed in apps.toml.

Examples:
    app add uv httpie -g cli-tools -d "Nicer cURL replacement"
    app add cask chromedriver -g utilities
    app add mas 6753110395
    app remove httpie
"""

import argparse
import json
import os
import re
import shutil
import subprocess  # noqa: S404
import sys
from collections.abc import Iterable
from pathlib import Path

import tomlkit

DOTPATH: Path = Path(os.environ.get("DOTPATH", Path(__file__).resolve().parent.parent))
APPS_TOML: Path = DOTPATH / "apps.toml"
APP_SOURCES: frozenset[str] = frozenset({"uv", "cask", "formula", "mas"})


class AppManagerError(Exception):
    """Custom exception for app management errors."""


def parse_args() -> argparse.Namespace:
    """Parses the command line arguments.

    Returns:
        An argparse.Namespace object.
    """
    parser = argparse.ArgumentParser(description="Manage entries in apps.toml")
    parser.add_argument(
        "--apps-file",
        default=APPS_TOML,
        type=Path,
        help=f"Path to apps.toml (default: {APPS_TOML})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add an app to apps.toml")
    add_parser.add_argument(
        "source",
        choices=list(APP_SOURCES),
        help=f"Source of the app (choices: {', '.join(APP_SOURCES)})",
    )
    add_parser.add_argument("app", help="App name or identifier")
    add_parser.add_argument(
        "-g",
        "--group",
        required=False,
        help="Section/group name in apps.toml (if omitted, you'll be prompted to pick one)",
    )
    add_parser.add_argument(
        "-d",
        "--description",
        help=(
            "Description for the app. Required for 'uv' sources; optional overrides for other"
            " sources."
        ),
    )

    remove_parser = subparsers.add_parser("remove", help="Remove an app from apps.toml")
    remove_parser.add_argument("app", help="App name or identifier to remove")

    return parser.parse_args()


def load_apps(apps_file: Path) -> tomlkit.TOMLDocument:
    """Loads the apps.toml file.

    Args:
        apps_file: The path to the apps.toml file.

    Returns:
        A tomlkit.TOMLDocument object.

    Raises:
        AppManagerError: If the apps.toml file is not found.
    """
    if not apps_file.exists():
        raise AppManagerError(f"apps.toml not found at {apps_file}")
    with apps_file.open("r", encoding="utf-8") as f:
        return tomlkit.parse(f.read())


def save_apps(apps_file: Path, doc: tomlkit.TOMLDocument) -> None:
    """Saves the apps.toml file.

    Args:
        apps_file: The path to the apps.toml file.
        doc: The tomlkit.TOMLDocument object to save.
    """
    with apps_file.open("w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(doc))


def infer_description(source: str, app: str, description: str | None) -> str:
    """Infers a description for an app.

    Args:
        source: The source of the app.
        app: The name of the app.
        description: The user-provided description of the app, if any.

    Returns:
        The final description of the app.

    Raises:
        AppManagerError: If the description is required for uv-installed apps
            and not provided.
    """
    if source == "uv" and not description:
        raise AppManagerError(
            "Description is required for uv-installed apps. Use --description/-d."
        )

    if description:
        return description

    if source == "mas":
        return fetch_mas_description(app)

    return fetch_brew_description(app, source)


def fetch_mas_description(app_id: str) -> str:
    """Fetches the description for an app from Mac App Store.

    Args:
        app_id: The ID of the app.

    Returns:
        The description of the app.

    Raises:
        AppManagerError: If the app is not found, the description cannot be
            fetched, or mas is not installed.
    """
    mas_executable: str | None = shutil.which("mas")
    if not mas_executable:
        raise AppManagerError("mas is required to infer descriptions for Mac App Store apps.")

    result = subprocess.run(  # noqa: S603
        [mas_executable, "info", app_id],
        check=False,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        msg: str = result.stderr.strip() or result.stdout.strip() or "Unable to fetch mas info."
        raise AppManagerError(msg)

    description_line = next(
        (line.strip() for line in result.stdout.splitlines() if line.strip()), None
    )
    if not description_line:
        raise AppManagerError("Could not parse mas info output.")

    match = re.match(r"^(?P<name>.+?)\s+\d[\w.\-]+(?:\s+\[.*\])?$", description_line)
    if match:
        return match.group("name").strip()

    return description_line


def fetch_brew_description(app: str, source: str) -> str:
    """Fetches the description for an app from Homebrew.

    Args:
        app: The name of the app.
        source: The source of the app.

    Returns:
        The description of the app.

    Raises:
        AppManagerError: If the app is not found, the description cannot be
            fetched or Homebrew is not installed.
    """
    brew_executable = shutil.which("brew")
    if not brew_executable:
        raise AppManagerError(
            "Homebrew is required to infer descriptions for cask/formula sources."
        )

    command: list[str] = [brew_executable, "info", "--json=v2"]
    if source == "cask":
        command.append("--cask")
    command.append(app)

    result = subprocess.run(command, check=False, text=True, capture_output=True)  # noqa: S603
    if result.returncode != 0:
        msg: str = result.stderr.strip() or result.stdout.strip() or "Unable to fetch brew info."
        raise AppManagerError(msg)

    data: dict[str, object] = json.loads(result.stdout)
    entries_key: str = "casks" if source == "cask" else "formulae"
    entries: list[dict[str, object]] = data.get(entries_key, [])
    if not entries:
        raise AppManagerError(f"No {entries_key} information returned for {app}.")

    entry: dict[str, object] = entries[0]
    description: str | None = entry.get("desc")
    if not description:
        raise AppManagerError(
            f"Could not determine description for {app}. Provide --description explicitly."
        )

    return str(description)


def sorted_table(items: Iterable[tuple[str, tomlkit.items.Item]]) -> tomlkit.items.Table:
    """Sorts a table of items by key.

    Args:
        items: The items to sort.

    Returns:
        A sorted tomlkit.items.Table object.
    """
    new_table = tomlkit.table()
    for item_key, item_value in sorted(items, key=lambda item: item[0].lower()):
        new_table[item_key] = item_value
    return new_table


def upsert_value(
    table: tomlkit.items.Table, key: str, value: tomlkit.items.Item
) -> tuple[tomlkit.items.Table, bool]:
    """Upserts a value into a table.

    Args:
        table: The table to upsert the value into.
        key: The key of the value to upsert.
        value: The value to upsert.

    Returns:
        A tuple of the sorted table and a boolean indicating if the value
            already existed.
    """
    items = list(table.items())
    for index, (item_key, _) in enumerate(items):
        if item_key == key:
            items[index] = (key, value)
            return sorted_table(items), True

    items.append((key, value))
    return sorted_table(items), False


def pick_group_interactively(document: tomlkit.TOMLDocument) -> str:
    def prompt_non_empty(prompt: str) -> str:
        while True:
            value = input(prompt).strip()
            if value:
                return value
            print("Group name cannot be empty.")

    groups: list[str] = [
        group for group, table in document.items() if isinstance(table, tomlkit.items.Table)
    ]
    if not groups:
        raise AppManagerError("No groups found in apps.toml to choose from.")

    if not sys.stdin.isatty():
        raise AppManagerError(
            "No --group/-g provided and stdin is not interactive. Provide --group explicitly."
        )

    print("No group provided. Select which group to add the app to:\n")
    print(" 0. <create a new group>")
    print("\n".join(f"{index:>2}. {group}" for index, group in enumerate(groups, start=1)))

    by_lower: dict[str, str] = {group.lower(): group for group in groups}

    while True:
        try:
            choice = input("\nEnter number, existing name, or new group name: ").strip()
        except (EOFError, KeyboardInterrupt) as exc:
            print()
            raise AppManagerError("No group selected.") from exc

        if not choice:
            continue

        if choice.isdigit():
            index = int(choice)
            if index == 0:
                return prompt_non_empty("New group name: ")
            if 1 <= index <= len(groups):
                return groups[index - 1]
            print("Invalid selection. Try again.")
            continue
        existing = by_lower.get(choice.lower())
        if existing is not None:
            return existing
        # Not an existing group: treat as a new group name.
        return choice

        print("Invalid selection. Try again.")


def add_app(document: tomlkit.TOMLDocument, args: argparse.Namespace) -> None:
    if not args.group:
        args.group = pick_group_interactively(document)

    description: str = infer_description(args.source, args.app, args.description)
    group_table = document.get(args.group)
    if group_table is None:
        group_table = tomlkit.table()
        document[args.group] = group_table
    if not isinstance(group_table, tomlkit.items.Table):
        raise AppManagerError(f"Section [{args.group}] is not a table in apps.toml.")

    value = tomlkit.string(args.source)
    value.comment(description)
    value.trivia.comment_ws = "  "  # two spaces before comment

    document[args.group], existed = upsert_value(group_table, args.app, value)
    if existed:
        print(
            f"🔄 Updated {args.app!r} in [{args.group}] with source '{args.source}' and"
            f' description "{description}".'
        )
    else:
        print(
            f"✅ Added {args.app!r} to [{args.group}] with source '{args.source}' and description"
            f' "{description}".'
        )


def remove_app(document: tomlkit.TOMLDocument, app: str) -> bool:
    for group, table in document.items():
        if not isinstance(table, tomlkit.items.Table):
            continue
        if app in table:
            items = [(key, value) for key, value in table.items() if key != app]
            document[group] = sorted_table(items)
            print(f"🗑️ Removed {app!r} from [{group}].")
            return True
    print(f"⚠️ {app!r} not found in apps.toml.")
    return False


def main() -> None:
    args: argparse.Namespace = parse_args()
    document: tomlkit.TOMLDocument = load_apps(args.apps_file)

    if args.command == "add":
        add_app(document, args)
    elif args.command == "remove":
        remove_app(document, args.app)

    save_apps(args.apps_file, document)


if __name__ == "__main__":
    try:
        main()
    except AppManagerError as error:
        raise SystemExit(f"❌ {error}") from None
