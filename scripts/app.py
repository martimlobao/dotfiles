#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "tomlkit>=0.13.2,<0.14",
# ]
# [tool.uv]
# exclude-newer = "2025-12-16T00:00:00Z"
# ///

"""Manage and install applications listed in apps.toml.

Examples:
    app add httpie uv -g cli-tools -d "Nicer cURL replacement"
    app add chromedriver cask -g utilities
    app add 6753110395 mas
    app remove httpie
    app remove chromedriver --no-install
    app list
    app sync

By default, ``app add`` installs the app and ``app remove`` uninstalls it. Use
``--no-install`` to skip these actions and only update ``apps.toml``.
"""

import argparse
import json
import os
import re
import shutil
import subprocess  # noqa: S404
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import tomlkit
from tomlkit.items import Item, Table

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None

DOTPATH: Path = Path(os.environ.get("DOTPATH", Path(__file__).resolve().parent.parent))
APPS_TOML: Path = DOTPATH / "apps.toml"
APP_SOURCES: frozenset[str] = frozenset({"uv", "cask", "formula", "mas"})
SOURCE_FLAG_ARGS: dict[str, str] = {
    "cask": "install_cask",
    "formula": "install_formula",
    "uv": "install_uv",
    "mas": "install_mas",
}


class AppManagerError(Exception):
    """Custom exception for app management errors."""


@dataclass
class AppInfo:
    name: str
    source: str
    description: str | None
    website: str | None
    version: str | None
    installed: bool


@dataclass
class InstalledState:
    casks: set[str]
    formulas: set[str]
    uv: set[str]
    mas: dict[str, str]


def _get_executable(name: str) -> str:
    path: str | None = shutil.which(name)
    if not path:
        raise AppManagerError(f"Required executable not found on PATH: {name}")
    return path


def _run(
    command: list[str],
    *,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        command,
        check=False,
        text=True,
        capture_output=capture_output,
    )
    if check and result.returncode != 0:
        stderr: str = (result.stderr or "").strip()
        stdout: str = (result.stdout or "").strip()
        details: str = stderr or stdout or f"Command failed with exit code {result.returncode}"
        raise AppManagerError(f"Command failed: {' '.join(command)}\n{details}")
    return result


def parse_args() -> argparse.Namespace:
    """Parses the command line arguments.

    Returns:
        An argparse.Namespace object.
    """
    parser = argparse.ArgumentParser(description="Manage and install applications using apps.toml")
    parser.add_argument(
        "--apps-file",
        default=APPS_TOML,
        type=Path,
        help=f"Path to apps.toml (default: {APPS_TOML})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add an app to apps.toml and install it")
    add_parser.add_argument("app", help="App name or identifier")
    add_parser.add_argument(
        "source",
        choices=list(APP_SOURCES),
        help=f"Source of the app (choices: {', '.join(APP_SOURCES)})",
    )
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
    add_parser.add_argument(
        "--no-install",
        action="store_true",
        help="Skip installing or uninstalling apps and only update the apps.toml file",
    )

    remove_parser = subparsers.add_parser(
        "remove", help="Remove an app from apps.toml and uninstall it"
    )
    remove_parser.add_argument("app", help="App name or identifier to remove")
    remove_parser.add_argument(
        "--no-install",
        action="store_true",
        help="Skip installing or uninstalling apps and only update the apps.toml file",
    )

    subparsers.add_parser("list", help="List apps in apps.toml")

    sync_parser = subparsers.add_parser(
        "sync",
        help=(
            "Install/update apps from apps.toml and optionally remove unmanaged apps "
            "(install/update/sync workflow)"
        ),
    )
    sync_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto-confirm uninstall prompts",
    )
    sync_parser.add_argument(
        "--no-cask",
        action="store_false",
        dest="install_cask",
        default=True,
        help="Disable cask install/sync/upgrade",
    )
    sync_parser.add_argument(
        "--no-formula",
        action="store_false",
        dest="install_formula",
        default=True,
        help="Disable formula install/sync/upgrade",
    )
    sync_parser.add_argument(
        "--no-uv",
        action="store_false",
        dest="install_uv",
        default=True,
        help="Disable uv install/sync/upgrade",
    )
    sync_parser.add_argument(
        "--no-mas",
        action="store_false",
        dest="install_mas",
        default=True,
        help="Disable mas install/sync/upgrade",
    )

    info_parser = subparsers.add_parser("info", help="Show app details")
    info_parser.add_argument("app", help="App name or identifier")
    info_parser.add_argument(
        "source",
        choices=list(APP_SOURCES),
        help=f"Source of the app (choices: {', '.join(APP_SOURCES)})",
    )

    return parser.parse_args()


def iter_group_tables(
    document: tomlkit.TOMLDocument,
) -> Iterator[tuple[str, Table]]:
    """Yields (group_name, table) pairs for all table sections.

    Args:
        document: The TOML document object.

    Yields:
        A tuple containing the group name and table.
    """
    for group, table in document.items():
        if isinstance(table, Table):
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


def find_app_group(document: tomlkit.TOMLDocument, app: str) -> tuple[str, str, str] | None:
    """Finds an app across all sections (case-insensitive).

    Args:
        document: The TOML document object.
        app: The name of the app.

    Returns:
        (app_key, app_source, app_group) if found, else None.
    """
    for group, table in iter_group_tables(document):
        for key in table:
            if normalize_key(key) == normalize_key(app):
                return key, str(table[key]), group
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
    if not isinstance(table, Table):
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


def infer_description(
    source: str, app: str, description: str | None, document: tomlkit.TOMLDocument
) -> str:
    """Infers a description for an app.

    Args:
        source: The source of the app.
        app: The name of the app.
        description: The user-provided description of the app, if any.
        document: The TOML document object.

    Returns:
        The final description of the app.

    Raises:
        AppManagerError: If the description is required for uv-installed apps
            and not provided.
    """
    if description is not None:
        description = description.strip()

    if source == "uv" and not description:
        raise AppManagerError(
            "Description is required for uv-installed apps. Use --description/-d."
        )

    if description:
        return description

    info: AppInfo = fetch_app_info(source, app, document)
    if info.description:
        return info.description
    raise AppManagerError(
        f"Could not determine description for {app}. Provide --description explicitly."
    )


def sanitize_toml_inline_comment(comment: str) -> str:
    """Make a string safe to use as a TOML inline comment.

    TOML comments cannot span multiple lines, so we collapse all newlines into
    single spaces.

    Returns:
        A single-line string safe to pass to ``tomlkit``'s
        ``value.comment(...)``.
    """
    return " ".join(comment.splitlines())


def fetch_mas_info(app_id: str) -> AppInfo:
    """Fetches info for an app from the Mac App Store.

    Args:
        app_id: The ID of the app.

    Returns:
        An AppInfo object.

    Raises:
        AppManagerError: If mas is not installed or if the app is not found.
    """
    mas: str = _get_executable("mas")

    result: subprocess.CompletedProcess[str] = _run([mas, "info", app_id])

    description_line: str | None = None
    website: str | None = None
    for raw_line in result.stdout.splitlines():
        stripped: str = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("From:"):
            website = stripped.split(":", 1)[1].strip() or None
            continue
        if description_line is None:
            description_line = stripped

    if not description_line:
        raise AppManagerError("Could not parse mas info output.")

    match: re.Match[str] | None = re.match(
        r"^(?P<name>.+?)\s+(?P<version>\d[\w.\-]+)(?:\s+\[.*\])?$",
        description_line,
    )
    name: str = description_line
    version: str | None = None
    if match:
        name = match.group("name").strip()
        version = match.group("version")

    list_result: subprocess.CompletedProcess[str] = _run([mas, "list"])

    installed_ids: set[str] = {
        line.split()[0]
        for line in list_result.stdout.splitlines()
        if line.strip() and line.split()[0].isdigit()
    }

    return AppInfo(
        name=app_id,
        source="mas",
        description=name,
        website=website,
        version=version,
        installed=app_id in installed_ids,
    )


def _extract_brew_install(entry: dict[str, JSON]) -> tuple[bool, str | None]:
    installed_field: JSON = entry.get("installed")
    version: str | None = None
    match installed_field:
        case list() if installed_field:
            first = installed_field[0]
            if isinstance(first, dict):
                version = str(first.get("version")) if first.get("version") else None
            return True, version
        case str() as installed_version if installed_version:
            version = installed_version
            return True, version
    versions: JSON = entry.get("versions")
    if isinstance(versions, dict):
        version_value: JSON = versions.get("stable") or versions.get("version")
        if isinstance(version_value, str):
            version = version_value
    return False, version


def fetch_brew_info(app: str, source: str) -> AppInfo:
    """Fetches info for an app from Homebrew.

    Args:
        app: The name of the app.
        source: The source of the app.

    Returns:
        An AppInfo object.

    Raises:
        AppManagerError: If Homebrew is not installed or if the app is not
            found.
    """
    brew: str = _get_executable("brew")
    command: list[str] = [brew, "info", "--json=v2"]
    if source == "cask":
        command.append("--cask")
    command.append(app)

    result: subprocess.CompletedProcess[str] = _run(command)

    data: dict[str, list[dict[str, JSON]]] = json.loads(result.stdout)
    entries_key: str = "casks" if source == "cask" else "formulae"
    entries: list[dict[str, JSON]] = data.get(entries_key, [])
    if not entries:
        raise AppManagerError(f"No {entries_key} information returned for {app}.")

    entry: dict[str, JSON] = entries[0]
    description: JSON = entry.get("desc")
    if description is not None and not isinstance(description, str):
        description = str(description)
    homepage: JSON = entry.get("homepage")
    website: str | None = None
    if isinstance(homepage, str) and homepage.strip():
        website = homepage.strip()
    installed, version = _extract_brew_install(entry)

    return AppInfo(
        name=app,
        source=source,
        description=str(description) if description else None,
        website=website,
        version=version,
        installed=installed,
    )


def fetch_uv_info(document: tomlkit.TOMLDocument, app: str) -> AppInfo:
    """Fetches info for an app from uv.

    Args:
        document: The TOML document object.
        app: The name of the app.

    Returns:
        An AppInfo object.
    """
    description: str | None = None
    entry = find_app_group(document, app)
    if entry is not None:
        key, _, group = entry
        table = document[group]
        if isinstance(table, Table):
            description = _get_item_comment(table[key])

    installed = False
    version: str | None = None
    uv: str = _get_executable("uv")
    result: subprocess.CompletedProcess[str] = _run([uv, "tool", "list"])
    for line in result.stdout.splitlines():
        name, version_ = line.split()
        if normalize_key(name) == normalize_key(app) and version_.startswith("v"):
            installed = True
            version = version_
            break

    return AppInfo(
        name=app,
        source="uv",
        description=description,
        website=f"https://pypi.org/project/{app}/",
        version=version,
        installed=installed,
    )


def fetch_app_info(source: str, app: str, document: tomlkit.TOMLDocument) -> AppInfo:
    """Fetches info for an app from a given source.

    Args:
        source: The source of the app.
        app: The name of the app.
        document: The TOML document object.

    Returns:
        An AppInfo object.

    Raises:
        AppManagerError: If the source is unknown.
    """
    match source:
        case "mas":
            return fetch_mas_info(app)
        case "cask" | "formula":
            return fetch_brew_info(app, source)
        case "uv":
            return fetch_uv_info(document, app)
    raise AppManagerError(f"Unknown source {source!r}.")


def sorted_table(items: Iterable[tuple[str, Item]]) -> Table:
    """Sorts a table of items by key.

    Args:
        items: The items to sort.

    Returns:
        A sorted TOMLKit Table object.
    """
    new_table = tomlkit.table()
    for item_key, item_value in sorted(items, key=lambda item: item[0].lower()):
        new_table[item_key] = item_value
    return new_table


def upsert_value(table: Table, key: str, value: Item) -> tuple[Table, bool]:
    """Upserts a value into a table.

    Args:
        table: The table to upsert the value into.
        key: The key of the value to upsert.
        value: The value to upsert.

    Returns:
        A tuple of the sorted table and a boolean indicating if the value
            already existed.
    """
    items: list[tuple[str, Item]] = list(table.items())
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

    groups: list[str] = [group for group, table in document.items() if isinstance(table, Table)]
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


def add_app(document: tomlkit.TOMLDocument, args: argparse.Namespace) -> tuple[bool, str | None]:
    """Adds an app to the apps.toml file.

    Args:
        document: The TOML document object.
        args: The argparse.Namespace object.

    Returns:
        A tuple of (source_changed, previous_source). `source_changed` is a
            boolean indicating whether the source changed as a result of this
            operation, and `previous_source` is that source if it existed,
            otherwise None.

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
    previous_source: str | None = None
    if existing is not None:
        existing_key, previous_source, existing_group = existing

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

    description: str = infer_description(args.source, args.app, args.description, document)
    group_table = document.get(args.group)
    if group_table is None:
        group_table = tomlkit.table()
        document[args.group] = group_table
    if not isinstance(group_table, Table):
        raise AppManagerError(f"Section [{args.group}] is not a table in apps.toml.")

    value = tomlkit.string(args.source)
    value.comment(sanitize_toml_inline_comment(description))
    value.trivia.comment_ws = "  "  # two spaces before comment

    document[args.group], existed = upsert_value(group_table, args.app, value)
    source_changed: bool = previous_source is not None and previous_source != args.source
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
    return source_changed, previous_source


def _package_command(*, source: str, app: str, install: bool) -> list[str]:
    action: str = "install" if install else "uninstall"
    match source:
        case "cask":
            command: list[str] = ["brew", action, "--cask", app]
        case "formula":
            command: list[str] = ["brew", action, "--formula", app]
        case "mas":
            command: list[str] = ["mas", action, app]
        case "uv":
            command: list[str] = ["uv", "tool", action, app]
        case _:
            raise AppManagerError(f"Unknown source {source!r}.")
    command[0] = _get_executable(command[0])
    return command


def _set_install_state(
    document: tomlkit.TOMLDocument, *, source: str, app: str, install: bool
) -> None:
    is_installed = fetch_app_info(source, app, document).installed
    if install and is_installed:
        print(f"✅ {app!r} is already installed via {source}.")
        return
    if not install and not is_installed:
        print(f"✅ {app!r} is not installed; skipping uninstall.")
        return

    if install:
        print(f"⬇️ Installing {app!r} via {source}...")
    else:
        print(f"🗑️ Uninstalling {app!r} via {source}...")

    command: list[str] = _package_command(source=source, app=app, install=install)
    _run(command)
    print(f"{'✅ Installed' if install else '🚮 Uninstalled'} {app!r}.")


def install_app(document: tomlkit.TOMLDocument, *, source: str, app: str) -> None:
    _set_install_state(document, source=source, app=app, install=True)


def uninstall_app(document: tomlkit.TOMLDocument, *, source: str, app: str) -> None:
    _set_install_state(document, source=source, app=app, install=False)


def remove_app(document: tomlkit.TOMLDocument, app: str) -> tuple[bool, str | None]:
    """Removes an app from the apps.toml file.

    Args:
        document: The TOML document object.
        app: The name of the app to remove.

    Returns:
        A tuple of a boolean indicating if the app was removed and its source.
    """
    existing: tuple[str, str, str] | None = find_app_group(document, app)
    if existing is None:
        print(f"⚠️ {app!r} not found in apps.toml.")
        return False, None

    existing_key, source, group = existing
    removed: bool = remove_app_from_group(document, group=group, app_key=existing_key)
    if not removed:
        print(f"⚠️ {app!r} not found in apps.toml.")
        return False, None

    print(f"🗑️ Removed {existing_key!r} from [{group}].")
    return True, source


class Ansi:
    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"
    DIM = "\x1b[2m"
    RED = "\x1b[31m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    BLUE = "\x1b[34m"
    MAGENTA = "\x1b[35m"
    CYAN = "\x1b[36m"


ANSI_RE: re.Pattern[str] = re.compile(r"\x1b\[[0-9;]*m")


def paint(
    text: str,
    style: str | None = None,
    *,
    icon: str = "",
    newline: bool = False,
    bold: bool = True,
    print_it: bool = True,
) -> str:
    """Format text with optional ANSI styling; optionally print it.

    Args:
        text: The text to format.
        style: Ansi color (e.g. Ansi.RED), Ansi.DIM, or None.
        icon: Optional icon prefix.
        newline: Prepend a newline.
        bold: Apply bold when style is a color. Default True.
        print_it: If True, print the result; if False, return only.

    Returns:
        The formatted string.
    """
    supports_color: bool = sys.stdout.isatty()
    has_styling: bool = bool(style) or bold
    if not supports_color or not has_styling:
        styled: str = text
    else:
        parts: list[str] = []
        if bold:
            parts.append(Ansi.BOLD)
        if style:
            parts.append(style)
        styled = "".join(parts) + text + Ansi.RESET
    full = ("\n" if newline else "") + (f"{icon} " if icon else "") + styled
    if print_it:
        print(full)
    return full


def _truncate(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def _visible_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


def _ljust_ansi(text: str, width: int) -> str:
    pad = width - _visible_len(text)
    if pad <= 0:
        return text
    return text + (" " * pad)


def _get_item_value(item: Item) -> str:
    value = getattr(item, "value", None)
    if value is None:
        return str(item).strip('"')
    return str(value)


def _get_item_comment(item: Item) -> str:
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
                return paint(s, Ansi.GREEN, bold=False, print_it=False)
            case "cask":
                return paint(s, Ansi.MAGENTA, bold=False, print_it=False)
            case "formula":
                return paint(s, Ansi.YELLOW, bold=False, print_it=False)
            case "mas":
                return paint(s, Ansi.BLUE, bold=False, print_it=False)
            case _:
                return s

    for group, group_rows in rows_by_group:
        if not group_rows:
            continue

        group_header = f"{group:<{col1_w}} | {'Source':<{source_w}} | {'Description':<{desc_w}}"
        paint(group_header, Ansi.CYAN)
        paint(sep, Ansi.DIM)

        for app, source, description in group_rows:
            desc = _truncate(description, desc_w)
            print(
                f"{_ljust_ansi(paint(app, print_it=False), col1_w)} | "
                f"{_ljust_ansi(color_source(source), source_w)} | "
                f"{paint(desc, Ansi.DIM, bold=False, print_it=False) if desc else ''}"
            )
        print()


def print_app_info(info: AppInfo) -> None:
    """Prints app info in a formatted table.

    Args:
        info: The AppInfo object.
    """
    fields: dict[str, str] = {
        "Name": info.name,
        "Source": info.source,
        "Description": info.description or "N/A",
        "Website": info.website or "N/A",
        "Version": info.version or "Unknown",
        "Installed": "Yes" if info.installed else "No",
    }

    max_label: int = max(len(label) for label in fields)
    for label, value in fields.items():
        print(f"{label:<{max_label}} : {value}")


def _list_installed_uv() -> list[str]:
    uv: str = _get_executable("uv")
    result = _run([uv, "tool", "list"])
    items: list[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("-"):
            continue
        items.append(stripped.split()[0])
    return items


def _list_installed_mas() -> dict[str, str]:
    mas: str = _get_executable("mas")
    result = _run([mas, "list"])
    apps: dict[str, str] = {}
    for line in result.stdout.splitlines():
        match = re.match(r"^(\d+)\s+(.+?)\s+\(.*\)$", line.strip())
        if not match:
            continue
        apps[match.group(1)] = match.group(2)
    return apps


def _confirm_uninstall(*, auto_yes: bool) -> bool:
    if auto_yes:
        return True
    prompt: str = paint(
        "Do you want to uninstall these apps? (y/n) ",
        Ansi.RED,
        icon="❓",
        print_it=False,
    )
    choice: str = input(prompt)
    return choice == "y"


def _iter_apps_by_source(document: tomlkit.TOMLDocument) -> dict[str, list[tuple[str, str]]]:
    by_source: dict[str, list[tuple[str, str]]] = {source: [] for source in APP_SOURCES}
    for group, table in iter_group_tables(document):
        for app, source in table.items():
            source_name = str(source)
            if source_name in by_source:
                by_source[source_name].append((group, str(app)))
    return by_source


def _source_enabled(source: str, args: argparse.Namespace) -> bool:
    field = SOURCE_FLAG_ARGS.get(source)
    return bool(field and getattr(args, field, False))


def _enabled_sources(args: argparse.Namespace) -> list[str]:
    return [source for source in SOURCE_FLAG_ARGS if _source_enabled(source, args)]


def _install_from_source(*, app: str, source: str, state: InstalledState) -> None:
    app_name: str = app.rsplit("/", maxsplit=1)[-1]
    is_installed: bool
    installed_name: str

    match source:
        case "cask":
            is_installed = app_name in state.casks
            installed_name = app_name
        case "formula":
            is_installed = app_name in state.formulas
            installed_name = app_name
        case "uv":
            is_installed = app in state.uv
            installed_name = app
        case "mas":
            is_installed = app in state.mas
            installed_name = state.mas.get(app, app)
        case _:
            raise AppManagerError(f"Unknown installation source: {source}.")

    if is_installed:
        paint(f"{installed_name} is already installed.", Ansi.GREEN, icon="✅")
        return

    paint(f"Installing {app}...", Ansi.BLUE, icon="⬇️")
    command = _package_command(source=source, app=app, install=True)
    _run(command, capture_output=False)


def _build_installed_state(args: argparse.Namespace) -> InstalledState:
    state = InstalledState(casks=set(), formulas=set(), uv=set(), mas={})
    if args.install_cask or args.install_formula:
        brew = _get_executable("brew")
        state.casks = set(_run([brew, "list", "--cask"]).stdout.split())
        state.formulas = set(_run([brew, "list", "--formula"]).stdout.split())
    if args.install_uv:
        state.uv = set(_list_installed_uv())
    if args.install_mas:
        state.mas = _list_installed_mas()
    return state


def _install_declared_apps(
    document: tomlkit.TOMLDocument, args: argparse.Namespace, state: InstalledState
) -> None:
    current_group: str | None = None
    for group, table in iter_group_tables(document):
        for app, source in table.items():
            source_name = str(source)
            if not _source_enabled(source_name, args):
                continue

            if group != current_group:
                suffix = "" if group.endswith("s") else " apps"
                paint(
                    f"Installing {group}{suffix}...",
                    Ansi.MAGENTA,
                    icon="📦",
                    newline=True,
                )
                current_group = group

            _install_from_source(app=str(app), source=source_name, state=state)


def _print_missing_apps(header: str, items: list[str]) -> None:
    paint(header, Ansi.RED, icon="❗️")
    for item in items:
        print(f"  {item}")


def _sync_homebrew(
    apps_by_source: dict[str, list[tuple[str, str]]], args: argparse.Namespace
) -> None:
    if not (args.install_cask or args.install_formula):
        return

    brew = _get_executable("brew")
    managed = {name for _, name in apps_by_source["cask"] + apps_by_source["formula"]}
    managed |= {name.rsplit("/", maxsplit=1)[-1] for name in managed}

    missing_formulae = (
        sorted(set(_run([brew, "leaves"]).stdout.split()) - managed)
        if args.install_formula
        else []
    )
    missing_casks = (
        sorted(set(_run([brew, "list", "--cask"]).stdout.split()) - managed)
        if args.install_cask
        else []
    )
    missing = missing_formulae + missing_casks

    if not missing:
        paint(
            "All Homebrew-installed formulae and casks are present in apps.toml.",
            Ansi.GREEN,
            icon="✅",
        )
        return

    _print_missing_apps(
        "The following Homebrew-installed formulae and casks are missing from apps.toml:",
        missing,
    )
    if not _confirm_uninstall(auto_yes=args.yes):
        paint("No apps were uninstalled.", Ansi.MAGENTA, icon="🆗")
        return

    for app in missing_formulae:
        paint(f"Uninstalling {app}...", Ansi.MAGENTA, icon="🗑️")
        _run([brew, "uninstall", app], capture_output=False)
        paint(f"Uninstalled {app}.", Ansi.MAGENTA, icon="🚮")
    for app in missing_casks:
        paint(f"Uninstalling {app}...", Ansi.MAGENTA, icon="🗑️")
        _run([brew, "uninstall", "--cask", "--zap", app], capture_output=False)
        paint(f"Uninstalled {app}.", Ansi.MAGENTA, icon="🚮")


def _sync_missing(header: str, ok_message: str, missing: list[str], *, auto_yes: bool) -> bool:
    if not missing:
        paint(ok_message, Ansi.GREEN, icon="✅")
        return False

    _print_missing_apps(header, missing)
    if not _confirm_uninstall(auto_yes=auto_yes):
        paint("No apps were uninstalled.", Ansi.MAGENTA, icon="🆗")
        return False
    return True


def _sync_uv(apps_by_source: dict[str, list[tuple[str, str]]], args: argparse.Namespace) -> None:
    if not args.install_uv:
        return

    managed_uv = {name for _, name in apps_by_source["uv"]}
    missing_uv = sorted(set(_list_installed_uv()) - managed_uv)
    if not _sync_missing(
        "The following uv-installed apps are missing from apps.toml:",
        "All uv-installed apps are present in apps.toml.",
        missing_uv,
        auto_yes=args.yes,
    ):
        return

    uv = _get_executable("uv")
    for app in missing_uv:
        _run([uv, "tool", "uninstall", app], capture_output=False)
        paint(f"Uninstalled {app}.", Ansi.MAGENTA, icon="🚮")


def _sync_mas(apps_by_source: dict[str, list[tuple[str, str]]], args: argparse.Namespace) -> None:
    if not args.install_mas:
        return

    installed_mas_now = _list_installed_mas()
    managed_mas = {name for _, name in apps_by_source["mas"]}
    missing_mas = {
        app_id: name for app_id, name in installed_mas_now.items() if app_id not in managed_mas
    }
    missing_items = [f"{name} ({app_id})" for app_id, name in sorted(missing_mas.items())]
    if not _sync_missing(
        "The following Mac App Store apps are missing from apps.toml:",
        "All Mac App Store apps are present in apps.toml.",
        missing_items,
        auto_yes=args.yes,
    ):
        return

    mas = _get_executable("mas")
    for app_id, name in sorted(missing_mas.items()):
        result = _run([mas, "uninstall", app_id], check=False, capture_output=False)
        if result.returncode != 0:
            paint(
                f"Failed to uninstall {name} ({app_id}). Please uninstall it manually.",
                Ansi.RED,
                icon="❌",
            )
            continue
        paint(f"Uninstalled {name} ({app_id}).", Ansi.MAGENTA, icon="🚮")


def _update_and_cleanup(args: argparse.Namespace) -> None:
    paint(
        "Updating existing apps and packages...",
        Ansi.MAGENTA,
        icon="🔼",
        newline=True,
    )
    if args.install_cask or args.install_formula:
        brew = _get_executable("brew")
        _run([brew, "update"], capture_output=False)
        _run([brew, "upgrade"], capture_output=False)
        _run([brew, "cleanup"], capture_output=False)
    if args.install_uv:
        uv = _get_executable("uv")
        _run([uv, "tool", "upgrade", "--all"], capture_output=False)
    if args.install_mas:
        mas = _get_executable("mas")
        _run([mas, "upgrade"], capture_output=False)


def sync_apps(document: tomlkit.TOMLDocument, args: argparse.Namespace) -> None:
    paint("Installing apps and packages...", Ansi.BLUE, icon="📲")
    sources = _enabled_sources(args)
    paint(
        f"Sources: {' '.join(sources) if sources else 'none'}",
        Ansi.BLUE,
        icon="📋",
    )

    apps_by_source = _iter_apps_by_source(document)
    _install_declared_apps(document, args, _build_installed_state(args))

    paint(
        "Syncing installed apps to apps.toml...",
        Ansi.MAGENTA,
        icon="🔄",
        newline=True,
    )
    _sync_homebrew(apps_by_source, args)
    _sync_uv(apps_by_source, args)
    _sync_mas(apps_by_source, args)
    _update_and_cleanup(args)


def main() -> None:
    """Main function.

    Raises:
        AppManagerError: If an unknown command is encountered.
    """
    args: argparse.Namespace = parse_args()
    document: tomlkit.TOMLDocument = load_apps(args.apps_file)

    if args.command == "add":
        source_changed, previous_source = add_app(document, args)
        save_apps(args.apps_file, document)
        if not args.no_install:
            if source_changed and previous_source in APP_SOURCES:
                uninstall_app(document, source=previous_source, app=args.app)
            install_app(document, source=args.source, app=args.app)
    elif args.command == "remove":
        removed, source = remove_app(document, args.app)
        if removed:
            # if nothing was removed there's no need to modify the file
            save_apps(args.apps_file, document)
            if source is not None and not args.no_install:
                uninstall_app(document, source=source, app=args.app)
    elif args.command == "list":
        list_apps(document)
    elif args.command == "info":
        info: AppInfo = fetch_app_info(args.source, args.app, document)
        print_app_info(info)
    elif args.command == "sync":
        sync_apps(document, args)
    else:
        raise AppManagerError(f"Unknown command: {args.command!r}")


if __name__ == "__main__":
    try:
        main()
    except AppManagerError as error:
        raise SystemExit(f"❌ {error}") from None
    except KeyboardInterrupt:
        raise SystemExit("\n❌ Operation cancelled by user.") from None
