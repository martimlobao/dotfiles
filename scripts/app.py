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
    app list
"""

import argparse
import json
import os
import re
import shutil
import subprocess  # noqa: S404
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

import tomlkit

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None

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

    subparsers.add_parser("list", help="List apps in apps.toml")

    return parser.parse_args()


def iter_group_tables(
    document: tomlkit.TOMLDocument,
) -> Iterator[tuple[str, tomlkit.items.Table]]:
    """Yields (group_name, table) pairs for all table sections.

    Args:
        document: The TOML document object.

    Yields:
        A tuple containing the group name and table.
    """
    for group, table in document.items():
        if isinstance(table, tomlkit.items.Table):
            yield group, table


def normalize_key(key: str) -> str:
    """Normalizes keys for global uniqueness checks.

    Args:
        key: The key to normalize.

    Returns:
        A normalized key used for comparisons.
    """
    return key.casefold()


def resolve_group_name(document: tomlkit.TOMLDocument, group: str) -> str:
    """Resolves a group name to an existing canonical group name.

    Matching is case-insensitive.

    If the provided group matches an existing group (ignoring case), returns
    the existing group's exact name from the file. Otherwise returns the
    stripped input (treated as a new group name).

    Args:
        document: The TOML document object.
        group: The group name to resolve.

    Returns:
        The resolved (canonical) group name to use.

    Raises:
        AppManagerError: If the provided group name is empty.
    """
    resolved: str = group.strip()
    if not resolved:
        raise AppManagerError("Group name cannot be empty.")

    by_norm: dict[str, str] = {
        normalize_key(existing): existing for existing, _ in iter_group_tables(document)
    }
    return by_norm.get(normalize_key(resolved), resolved)


def validate_no_duplicate_apps(document: tomlkit.TOMLDocument, *, apps_file: Path) -> None:
    """Ensures each app appears in only one section in the TOML.

    Args:
        document: The TOML document object.
        apps_file: The path to the apps.toml file.

    Raises:
        AppManagerError: If duplicates are found
    """
    seen: dict[str, tuple[str, str]] = {}  # norm_app -> (original_key, group)
    keys_by_norm: dict[str, set[str]] = {}
    groups_by_norm: dict[str, set[str]] = {}

    for group, table in iter_group_tables(document):
        for key in table:
            norm: str = normalize_key(str(key))
            keys_by_norm.setdefault(norm, set()).add(str(key))
            if norm in seen:
                # Only a problem if it appears in another section.
                first_group = seen[norm][1]
                if first_group != group:
                    groups_by_norm.setdefault(norm, set()).update({first_group, group})
            else:
                seen[norm] = (str(key), group)

    if not groups_by_norm:
        return

    lines: list[str] = [
        f"Duplicate apps found in {apps_file}. Each app must be globally unique.",
        "Please fix the file manually (move/remove the duplicates) and re-run.",
        "",
        "Duplicates:",
    ]
    for norm in sorted(groups_by_norm):
        groups = ", ".join(f"[{g}]" for g in sorted(groups_by_norm[norm], key=str.lower))
        keys = ", ".join(repr(k) for k in sorted(keys_by_norm.get(norm, {norm}), key=str.lower))
        lines.append(f"- {keys} appears in {groups}")

    raise AppManagerError("\n".join(lines))


def load_apps(apps_file: Path) -> tomlkit.TOMLDocument:
    """Loads the apps.toml file.

    Args:
        apps_file: The path to the apps.toml file.

    Returns:
        A TOML document object.
    """
    if not apps_file.exists():
        print(f"⚠️ apps.toml not found at {apps_file}, creating a new file.")
        document = tomlkit.document()
        with apps_file.open("w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(document))
        return document
    with apps_file.open("r", encoding="utf-8") as f:
        document = tomlkit.parse(f.read())

    validate_no_duplicate_apps(document, apps_file=apps_file)
    return document


def save_apps(apps_file: Path, document: tomlkit.TOMLDocument) -> None:
    """Saves the apps.toml file.

    Args:
        apps_file: The path to the apps.toml file.
        document: The TOML document object to save.
    """
    with apps_file.open("w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(document))


def find_app_group(document: tomlkit.TOMLDocument, app: str) -> tuple[str, str] | None:
    """Finds an app across all sections (case-insensitive).

    Args:
        document: The TOML document object.
        app: The name of the app.

    Returns:
        (group_name, existing_key) if found, else None.
    """
    norm: str = normalize_key(app)
    for group, table in iter_group_tables(document):
        for key in table:
            if normalize_key(str(key)) == norm:
                return group, str(key)
    return None


def remove_app_from_group(document: tomlkit.TOMLDocument, *, group: str, app_key: str) -> bool:
    """Removes an app key from a specific group table.

    Args:
        document: The TOML document object.
        group: The name of the group.
        app_key: The key of the app.

    Returns:
        A boolean indicating if the app was removed.
    """
    table = document.get(group)
    if not isinstance(table, tomlkit.items.Table):
        return False
    if app_key not in table:
        return False

    items = [(key, value) for key, value in table.items() if key != app_key]
    if not items:
        # Remove the whole section when it's empty.
        del document[group]
        return True

    document[group] = sorted_table(items)
    return True


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

    data: dict[str, list[dict[str, JSON]]] = json.loads(result.stdout)
    entries_key: str = "casks" if source == "cask" else "formulae"
    entries: list[dict[str, JSON]] = data.get(entries_key, [])
    if not entries:
        raise AppManagerError(f"No {entries_key} information returned for {app}.")

    entry: dict[str, JSON] = entries[0]
    description: JSON = entry.get("desc")
    if not description or not isinstance(description, str):
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
    """Picks a group interactively.

    Args:
        document: The TOML document object.

    Returns:
        The name of the group.

    Raises:
        AppManagerError: If the group is not found, the stdin is not
            interactive, or the group name is empty.
    """

    def prompt_non_empty(prompt: str) -> str:
        while True:
            try:
                value: str = input(prompt).strip()
            except (EOFError, KeyboardInterrupt) as exc:
                print()
                raise AppManagerError("No group selected.") from exc
            if value:
                return value
            print("Group name cannot be empty.")

    groups: list[str] = [
        group for group, table in document.items() if isinstance(table, tomlkit.items.Table)
    ]
    if not sys.stdin.isatty():
        raise AppManagerError(
            "No --group/-g provided and stdin is not interactive. Provide --group explicitly."
        )

    if not groups:
        # Empty apps.toml: allow user to create the first group.
        # Normalize anyway for consistency
        return resolve_group_name(document, prompt_non_empty("New group name: "))

    print("No group provided. Select which group to add the app to:\n")
    print(" 0. <create a new group>")
    print("\n".join(f"{index:>2}. {group}" for index, group in enumerate(groups, start=1)))

    by_norm: dict[str, str] = {normalize_key(group): group for group in groups}

    while True:
        try:
            choice: str = input("\nEnter number, existing name, or new group name: ").strip()
        except (EOFError, KeyboardInterrupt) as exc:
            print()
            raise AppManagerError("No group selected.") from exc

        if not choice:
            continue

        if choice.isdigit():
            index = int(choice)
            if index == 0:
                # If the user types a name that case-insensitively matches an
                # existing group, normalize to the canonical existing group
                # name to avoid duplicate sections.
                return resolve_group_name(document, prompt_non_empty("New group name: "))
            if 1 <= index <= len(groups):
                return groups[index - 1]
            print("Invalid selection. Try again.")
            continue
        existing: str | None = by_norm.get(normalize_key(choice))
        if existing is not None:
            return existing
        # Not an existing group: treat as a new group name.
        return resolve_group_name(document, choice)


def add_app(document: tomlkit.TOMLDocument, args: argparse.Namespace) -> None:
    """Adds an app to the apps.toml file.

    Args:
        document: The TOML document object.
        args: The argparse.Namespace object.

    Raises:
        AppManagerError: If unable to add the app to the apps.toml file.
    """
    if not args.group:
        args.group = pick_group_interactively(document)
    else:
        # Normalize CLI-provided group names to existing sections, so
        # `--group CLI-Tools` matches an existing `[cli-tools]`.
        args.group = resolve_group_name(document, args.group)

    existing = find_app_group(document, args.app)
    moved_from: str | None = None
    if existing is not None:
        existing_group, existing_key = existing
        # Keep the canonical key casing already in the file to avoid duplicates
        # like "Foo" vs "foo".
        args.app = existing_key
        if existing_group != args.group:
            removed = remove_app_from_group(document, group=existing_group, app_key=existing_key)
            if not removed:
                raise AppManagerError(
                    f"App {args.app!r} was detected in [{existing_group}] but could not be "
                    "removed."
                )
            moved_from = existing_group

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
    if moved_from is not None:
        print(
            f"➡️ Moved {args.app!r} from [{moved_from}] to [{args.group}] with source"
            f" '{args.source}' and description \"{description}\"."
        )
    elif existed:
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
    """Removes an app from the apps.toml file.

    Args:
        document: The TOML document object.
        app: The name of the app to remove.

    Returns:
        A boolean indicating if the app was removed.
    """
    existing: tuple[str, str] | None = find_app_group(document, app)
    if existing is None:
        print(f"⚠️ {app!r} not found in apps.toml.")
        return False

    group, existing_key = existing
    removed: bool = remove_app_from_group(document, group=group, app_key=existing_key)
    if not removed:
        print(f"⚠️ {app!r} not found in apps.toml.")
        return False

    print(f"🗑️ Removed {existing_key!r} from [{group}].")
    return True


class _Ansi:
    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"
    DIM = "\x1b[2m"
    CYAN = "\x1b[36m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    MAGENTA = "\x1b[35m"
    BLUE = "\x1b[34m"


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _supports_color() -> bool:
    return sys.stdout.isatty()


def _c(text: str, *styles: str) -> str:
    if not _supports_color() or not styles:
        return text
    return "".join(styles) + text + _Ansi.RESET


def _truncate(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def _visible_len(text: str) -> int:
    return len(_ANSI_RE.sub("", text))


def _ljust_ansi(text: str, width: int) -> str:
    pad = width - _visible_len(text)
    if pad <= 0:
        return text
    return text + (" " * pad)


def _get_item_value(item: tomlkit.items.Item) -> str:
    value = getattr(item, "value", None)
    if value is None:
        return str(item).strip('"')
    return str(value)


def _get_item_comment(item: tomlkit.items.Item) -> str:
    trivia = getattr(item, "trivia", None)
    comment = getattr(trivia, "comment", None)
    if not comment:
        return ""
    return str(comment).lstrip("#").strip()


def list_apps(document: tomlkit.TOMLDocument) -> None:
    """Lists apps in apps.toml in an aligned table.

    Args:
        document: The TOML document object.
    """
    groups = list(iter_group_tables(document))
    if not groups:
        print("No apps found.")
        return

    rows_by_group: list[tuple[str, list[tuple[str, str, str]]]] = []
    any_rows = False
    for group, table in groups:
        group_rows: list[tuple[str, str, str]] = []
        for app_key, item in table.items():
            app = str(app_key)
            source = _get_item_value(item)
            desc = _get_item_comment(item)
            group_rows.append((app, source, desc))
            any_rows = True
        rows_by_group.append((group, group_rows))

    if not any_rows:
        print("No apps found.")
        return

    # Compute widths once, across all groups, so every table aligns the same.
    all_rows = [row for _, rows in rows_by_group for row in rows]
    col1_w = max(
        (
            *(len(r[0]) for r in all_rows),
            *(len(group) for group, rows in rows_by_group if rows),
        ),
        default=0,
    )
    source_w: int = max((len("Source"), *(len(r[1]) for r in all_rows)))

    cols: int = shutil.get_terminal_size((120, 20)).columns
    fixed: int = col1_w + source_w + len(" |  | ")  # separators/spaces
    desc_w: int = max(10, cols - fixed)

    sep = f"{'-' * col1_w}-+-{'-' * source_w}-+-{'-' * desc_w}"

    def color_source(s: str) -> str:
        match s:
            case "uv":
                return _c(s, _Ansi.GREEN)
            case "cask":
                return _c(s, _Ansi.MAGENTA)
            case "formula":
                return _c(s, _Ansi.YELLOW)
            case "mas":
                return _c(s, _Ansi.BLUE)
            case _:
                return s

    for group, group_rows in rows_by_group:
        if not group_rows:
            continue

        group_header = f"{group:<{col1_w}} | {'Source':<{source_w}} | {'Description':<{desc_w}}"
        print(_c(group_header, _Ansi.CYAN, _Ansi.BOLD))
        print(_c(sep, _Ansi.DIM))

        for app, source, description in group_rows:
            desc = _truncate(description, desc_w)
            print(
                f"{_ljust_ansi(_c(app, _Ansi.BOLD), col1_w)} | "
                f"{_ljust_ansi(color_source(source), source_w)} | "
                f"{_c(desc, _Ansi.DIM) if desc else ''}"
            )
        print()


def main() -> None:
    """Main function.

    Raises:
        AppManagerError: If an unknown command is encountered.
    """
    args: argparse.Namespace = parse_args()
    document: tomlkit.TOMLDocument = load_apps(args.apps_file)

    if args.command == "add":
        add_app(document, args)
        save_apps(args.apps_file, document)
    elif args.command == "remove":
        removed: bool = remove_app(document, args.app)
        if removed:
            # if nothing was removed there's no need to modify the file
            save_apps(args.apps_file, document)
    elif args.command == "list":
        list_apps(document)
    else:
        raise AppManagerError(f"Unknown command: {args.command!r}")


if __name__ == "__main__":
    try:
        main()
    except AppManagerError as error:
        raise SystemExit(f"❌ {error}") from None
