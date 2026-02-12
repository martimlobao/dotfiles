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

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess  # noqa: S404
import sys
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import tomlkit
from tomlkit.items import Item, Table

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None

DOTPATH: Path = Path(os.environ.get("DOTPATH", Path(__file__).resolve().parent.parent))
APPS_TOML: Path = DOTPATH / "apps.toml"


class AppManagerError(Exception):
    """Raised for expected, user-facing app-management failures."""


@dataclass(slots=True, frozen=True)
class AppRecord:
    """Normalized app record from apps.toml."""

    group: str
    key: str
    source: str
    description: str


@dataclass(slots=True, frozen=True)
class AppInfo:
    """Resolved app information from an upstream source."""

    name: str
    source: str
    description: str | None
    website: str | None
    version: str | None
    installed: bool


@dataclass(slots=True, frozen=True)
class SourceConfig:
    """CLI configuration for a source strategy."""

    name: str
    install_flag: str
    sync_help: str


@dataclass(slots=True, frozen=True)
class SyncOptions:
    """Runtime options for sync execution."""

    yes: bool
    enabled_sources: set[str]


@dataclass(slots=True, frozen=True)
class UnmanagedApp:
    """Installed app that is not present in apps.toml."""

    source: str
    identifier: str
    display: str


@dataclass(slots=True, frozen=True)
class OperationResult:
    """Outcome for source install/uninstall operations."""

    success: bool
    message: str
    skipped: bool = False

    @classmethod
    def ok(cls, message: str) -> OperationResult:
        return cls(success=True, message=message, skipped=False)

    @classmethod
    def skipped_result(cls, message: str) -> OperationResult:
        return cls(success=True, message=message, skipped=True)

    @classmethod
    def failed(cls, message: str) -> OperationResult:
        return cls(success=False, message=message, skipped=False)


@dataclass(slots=True, frozen=True)
class AddAppOutcome:
    """Result of adding/updating an app in apps.toml."""

    app_key: str
    group: str
    description: str
    existed: bool
    moved_from: str | None
    previous_source: str | None

    @property
    def source_changed(self) -> bool:
        return bool(self.previous_source)


@dataclass(slots=True, frozen=True)
class RemoveAppOutcome:
    """Result of removing an app from apps.toml."""

    removed: bool
    app_key: str | None
    source: str | None
    group: str | None


class CommandRunner:
    """Thin subprocess wrapper with consistent errors and executable lookup."""

    def get_executable(self, name: str) -> str:  # noqa: PLR6301
        path: str | None = shutil.which(name)
        if not path:
            raise AppManagerError(f"Required executable not found on PATH: {name}")
        return path

    def run(  # noqa: PLR6301
        self,
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


class Ansi:
    """ANSI style constants."""

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
MIN_UV_LIST_COLUMNS: int = 2


class Console:
    """Terminal output and prompt helper."""

    def paint(  # noqa: PLR6301
        self,
        text: str,
        style: str | None = None,
        *,
        icon: str = "",
        newline: bool = False,
        bold: bool = True,
        print_it: bool = True,
    ) -> str:
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

        full: str = ("\n" if newline else "") + (f"{icon} " if icon else "") + styled
        if print_it:
            print(full)
        return full

    def prompt_yes_no(self, prompt: str, *, auto_yes: bool) -> bool:
        if auto_yes:
            return True
        rendered: str = self.paint(prompt, Ansi.RED, icon="❓", print_it=False)
        choice: str = input(rendered).strip().lower()
        return choice == "y"

    def print_missing(self, header: str, items: list[str]) -> None:
        self.paint(header, Ansi.RED, icon="❗️")
        for item in items:
            print(f"  {item}")

    def print_info(self, info: AppInfo) -> None:  # noqa: PLR6301
        fields: OrderedDict[str, str] = OrderedDict([
            ("Name", info.name),
            ("Source", info.source),
            ("Description", info.description or "N/A"),
            ("Website", info.website or "N/A"),
            ("Version", info.version or "Unknown"),
            ("Installed", "Yes" if info.installed else "No"),
        ])
        max_label: int = max(len(label) for label in fields)
        for label, value in fields.items():
            print(f"{label:<{max_label}} : {value}")

    def render_records(self, grouped_records: list[tuple[str, list[AppRecord]]]) -> None:
        if not grouped_records or all(not rows for _, rows in grouped_records):
            print("No apps found.")
            return

        rows: list[tuple[str, str, str]] = [
            (record.key, record.source, record.description)
            for _, records in grouped_records
            for record in records
        ]
        if not rows:
            print("No apps found.")
            return

        col1_w: int = max(
            (
                *(len(name) for name, _, _ in rows),
                *(len(group) for group, records in grouped_records if records),
            ),
            default=0,
        )
        source_w: int = max((len("Source"), *(len(source) for _, source, _ in rows)))

        cols: int = shutil.get_terminal_size((120, 20)).columns
        fixed: int = col1_w + source_w + len(" |  | ")
        desc_w: int = max(10, cols - fixed)
        sep: str = f"{'-' * col1_w}-+-{'-' * source_w}-+-{'-' * desc_w}"

        for group, records in grouped_records:
            if not records:
                continue
            header: str = f"{group:<{col1_w}} | {'Source':<{source_w}} | {'Description':<{desc_w}}"
            self.paint(header, Ansi.CYAN)
            self.paint(sep, Ansi.DIM)

            for record in records:
                source: str = self._color_source(record.source)
                desc: str = self._truncate(record.description, desc_w)
                print(
                    f"{self._ljust_ansi(self.paint(record.key, print_it=False), col1_w)} | "
                    f"{self._ljust_ansi(source, source_w)} | "
                    f"{self.paint(desc, Ansi.DIM, bold=False, print_it=False) if desc else ''}"
                )
            print()

    def emit_operation(self, result: OperationResult, *, success_style: str = Ansi.GREEN) -> None:
        if not result.success:
            self.paint(result.message, Ansi.RED, icon="❌")
            return
        if result.skipped:
            self.paint(result.message, Ansi.GREEN, icon="✅")
            return
        self.paint(result.message, success_style, icon="✅")

    def _color_source(self, source: str) -> str:
        match source:
            case "uv":
                return self.paint(source, Ansi.GREEN, bold=False, print_it=False)
            case "cask":
                return self.paint(source, Ansi.MAGENTA, bold=False, print_it=False)
            case "formula":
                return self.paint(source, Ansi.YELLOW, bold=False, print_it=False)
            case "mas":
                return self.paint(source, Ansi.BLUE, bold=False, print_it=False)
            case _:
                return source

    @staticmethod
    def _truncate(text: str, width: int) -> str:
        if width <= 0:
            return ""
        if len(text) <= width:
            return text
        if width <= 1:
            return text[:width]
        return text[: width - 1] + "…"

    @staticmethod
    def _visible_len(text: str) -> int:
        return len(ANSI_RE.sub("", text))

    def _ljust_ansi(self, text: str, width: int) -> str:
        pad: int = width - self._visible_len(text)
        if pad <= 0:
            return text
        return text + (" " * pad)


class AppsRepository:
    """All apps.toml read/write and record-manipulation concerns."""

    def __init__(self, apps_file: Path, *, console: Console) -> None:
        self.apps_file = apps_file
        self.console = console

    def load(self) -> tomlkit.TOMLDocument:
        if not self.apps_file.exists():
            self.console.paint(
                f"apps.toml not found at {self.apps_file}, creating a new file.",
                Ansi.YELLOW,
                icon="⚠️",
            )
            document = tomlkit.document()
            with self.apps_file.open("w", encoding="utf-8") as handle:
                handle.write(tomlkit.dumps(document))
            return document

        with self.apps_file.open("r", encoding="utf-8") as handle:
            document = tomlkit.parse(handle.read())

        self.validate_no_duplicates(document)
        return document

    def save(self, document: tomlkit.TOMLDocument) -> None:
        with self.apps_file.open("w", encoding="utf-8") as handle:
            handle.write(tomlkit.dumps(document))

    @staticmethod
    def normalize_key(key: str) -> str:
        return key.casefold()

    def iter_group_tables(  # noqa: PLR6301
        self,
        document: tomlkit.TOMLDocument,
    ) -> Iterator[tuple[str, Table]]:
        for group, table in document.items():
            if isinstance(table, Table):
                yield group, table

    def resolve_group_name(self, document: tomlkit.TOMLDocument, group: str) -> str:
        resolved: str = group.strip()
        if not resolved:
            raise AppManagerError("Group name cannot be empty.")

        by_norm: dict[str, str] = {
            self.normalize_key(existing): existing
            for existing, _ in self.iter_group_tables(document)
        }
        return by_norm.get(self.normalize_key(resolved), resolved)

    def validate_no_duplicates(self, document: tomlkit.TOMLDocument) -> None:
        seen: dict[str, tuple[str, str]] = {}
        keys_by_norm: dict[str, set[str]] = {}
        groups_by_norm: dict[str, set[str]] = {}

        for group, table in self.iter_group_tables(document):
            for key in table:
                norm: str = self.normalize_key(str(key))
                keys_by_norm.setdefault(norm, set()).add(str(key))
                if norm in seen:
                    first_group = seen[norm][1]
                    if first_group != group:
                        groups_by_norm.setdefault(norm, set()).update({first_group, group})
                else:
                    seen[norm] = (str(key), group)

        if not groups_by_norm:
            return

        lines: list[str] = [
            f"Duplicate apps found in {self.apps_file}. Each app must be globally unique.",
            "Please fix the file manually (move/remove the duplicates) and re-run.",
            "",
            "Duplicates:",
        ]
        for norm in sorted(groups_by_norm):
            groups: str = ", ".join(f"[{g}]" for g in sorted(groups_by_norm[norm], key=str.lower))
            keys: str = ", ".join(repr(key) for key in sorted(keys_by_norm[norm], key=str.lower))
            lines.append(f"- {keys} appears in {groups}")

        raise AppManagerError("\n".join(lines))

    @staticmethod
    def sanitize_toml_inline_comment(comment: str) -> str:
        return " ".join(comment.splitlines())

    @staticmethod
    def sorted_table(items: Iterable[tuple[str, Item]]) -> Table:
        table = tomlkit.table()
        for item_key, item_value in sorted(items, key=lambda item: item[0].lower()):
            table[item_key] = item_value
        return table

    def upsert_value(self, table: Table, key: str, value: Item) -> tuple[Table, bool]:
        items: list[tuple[str, Item]] = list(table.items())
        for index, (item_key, _) in enumerate(items):
            if item_key == key:
                items[index] = (key, value)
                return self.sorted_table(items), True

        items.append((key, value))
        return self.sorted_table(items), False

    def find_app(self, document: tomlkit.TOMLDocument, app: str) -> AppRecord | None:
        for group, table in self.iter_group_tables(document):
            for key, item in table.items():
                if self.normalize_key(str(key)) == self.normalize_key(app):
                    return AppRecord(
                        group=group,
                        key=str(key),
                        source=self.get_item_value(item),
                        description=self.get_item_comment(item),
                    )
        return None

    def remove_app_from_group(
        self,
        document: tomlkit.TOMLDocument,
        *,
        group: str,
        app_key: str,
    ) -> bool:
        table = document.get(group)
        if not isinstance(table, Table):
            return False
        if app_key not in table:
            return False

        items: list[tuple[str, Item]] = [
            (key, value) for key, value in table.items() if key != app_key
        ]
        if not items:
            del document[group]
            return True

        document[group] = self.sorted_table(items)
        return True

    def add_or_update(
        self,
        document: tomlkit.TOMLDocument,
        *,
        app: str,
        source: str,
        group: str,
        description: str,
    ) -> AddAppOutcome:
        existing: AppRecord | None = self.find_app(document, app)
        moved_from: str | None = None
        previous_source: str | None = None

        canonical_key: str = app
        target_group: str = self.resolve_group_name(document, group)

        if existing is not None:
            canonical_key = existing.key
            previous_source = existing.source
            if existing.group != target_group:
                removed: bool = self.remove_app_from_group(
                    document,
                    group=existing.group,
                    app_key=existing.key,
                )
                if not removed:
                    raise AppManagerError(
                        f"App {canonical_key!r} was detected in "
                        f"[{existing.group}] but could not be removed."
                    )
                moved_from = existing.group

        group_table = document.get(target_group)
        if group_table is None:
            group_table = tomlkit.table()
            document[target_group] = group_table
        if not isinstance(group_table, Table):
            raise AppManagerError(f"Section [{target_group}] is not a table in apps.toml.")

        value = tomlkit.string(source)
        value.comment(self.sanitize_toml_inline_comment(description))
        value.trivia.comment_ws = "  "

        document[target_group], existed = self.upsert_value(group_table, canonical_key, value)

        return AddAppOutcome(
            app_key=canonical_key,
            group=target_group,
            description=description,
            existed=existed,
            moved_from=moved_from,
            previous_source=previous_source,
        )

    def remove(self, document: tomlkit.TOMLDocument, app: str) -> RemoveAppOutcome:
        existing: AppRecord | None = self.find_app(document, app)
        if existing is None:
            return RemoveAppOutcome(removed=False, app_key=None, source=None, group=None)

        removed: bool = self.remove_app_from_group(
            document,
            group=existing.group,
            app_key=existing.key,
        )
        if not removed:
            return RemoveAppOutcome(removed=False, app_key=None, source=None, group=None)

        return RemoveAppOutcome(
            removed=True,
            app_key=existing.key,
            source=existing.source,
            group=existing.group,
        )

    def list_grouped_records(
        self,
        document: tomlkit.TOMLDocument,
    ) -> list[tuple[str, list[AppRecord]]]:
        grouped: list[tuple[str, list[AppRecord]]] = []
        for group, table in self.iter_group_tables(document):
            records: list[AppRecord] = []
            for key, item in table.items():
                records.append(
                    AppRecord(
                        group=group,
                        key=str(key),
                        source=self.get_item_value(item),
                        description=self.get_item_comment(item),
                    )
                )
            grouped.append((group, records))
        return grouped

    def list_records(self, document: tomlkit.TOMLDocument) -> list[AppRecord]:
        return [record for _, records in self.list_grouped_records(document) for record in records]

    @staticmethod
    def get_item_value(item: Item) -> str:
        value = getattr(item, "value", None)
        if value is None:
            return str(item).strip('"')
        return str(value)

    @staticmethod
    def get_item_comment(item: Item) -> str:
        trivia = getattr(item, "trivia", None)
        comment = getattr(trivia, "comment", None)
        if not comment:
            return ""
        return str(comment).lstrip("#").strip()


class SourceRegistry:
    """Factory/registry for source strategies."""

    _service_classes: ClassVar[dict[str, type[BaseSourceService]]] = {}

    @classmethod
    def register(cls, service_cls: type[BaseSourceService]) -> None:
        name: str = service_cls.source_name
        if not name:
            return
        if name in cls._service_classes:
            raise AppManagerError(f"Duplicate source registration for {name!r}.")
        cls._service_classes[name] = service_cls

    @classmethod
    def source_names(cls) -> list[str]:
        return list(cls._service_classes)

    @classmethod
    def source_configs(cls) -> list[SourceConfig]:
        return [
            service_cls.config()
            for _, service_cls in sorted(cls._service_classes.items(), key=itemgetter(0))
        ]

    @classmethod
    def create(
        cls,
        source: str,
        *,
        runner: CommandRunner,
        console: Console,
    ) -> BaseSourceService:
        service_cls = cls._service_classes.get(source)
        if service_cls is None:
            raise AppManagerError(f"Unknown source {source!r}.")
        return service_cls(runner=runner, console=console)


class BaseSourceService(ABC):
    """Strategy base class.

    Uses template methods for install and uninstall flows.
    """

    source_name: ClassVar[str] = ""
    install_flag: ClassVar[str] = ""
    sync_toggle_help: ClassVar[str] = ""
    provider_name: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls.source_name:
            SourceRegistry.register(cls)

    def __init__(self, *, runner: CommandRunner, console: Console) -> None:
        self.runner = runner
        self.console = console

    @classmethod
    def config(cls) -> SourceConfig:
        return SourceConfig(
            name=cls.source_name,
            install_flag=cls.install_flag,
            sync_help=cls.sync_toggle_help,
        )

    @property
    def maintenance_key(self) -> str:
        return self.provider_name or self.source_name

    def managed_aliases(self, app: str) -> set[str]:  # noqa: PLR6301
        return {app}

    def pre_install_check(self, app: str) -> OperationResult | None:  # noqa: PLR6301
        del app
        return None

    def is_installed(self, app: str) -> bool:
        aliases: set[str] = {alias.casefold() for alias in self.managed_aliases(app)}
        installed_map: dict[str, str] = self.list_installed()
        installed_tokens: set[str] = {
            token.casefold() for token in {*installed_map.keys(), *installed_map.values()}
        }
        return bool(aliases & installed_tokens)

    def ensure_installed(self, app: str) -> OperationResult:
        if self.is_installed(app):
            return OperationResult.skipped_result(
                f"{app!r} is already installed via {self.source_name}."
            )

        preflight: OperationResult | None = self.pre_install_check(app)
        if preflight is not None:
            return preflight

        self.console.paint(f"Installing {app!r} via {self.source_name}...", Ansi.BLUE, icon="⬇️")
        self.install(app)
        return OperationResult.ok(f"Installed {app!r}.")

    def ensure_uninstalled(self, app: str) -> OperationResult:
        if not self.is_installed(app):
            return OperationResult.skipped_result(f"{app!r} is not installed; skipping uninstall.")

        self.console.paint(
            f"Uninstalling {app!r} via {self.source_name}...", Ansi.MAGENTA, icon="🗑️"
        )
        result: OperationResult = self.uninstall(app)
        if result.success and not result.skipped:
            return OperationResult.ok(f"Uninstalled {app!r}.")
        return result

    @abstractmethod
    def fetch_info(
        self, app: str, *, repo: AppsRepository, document: tomlkit.TOMLDocument
    ) -> AppInfo:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def list_installed(self) -> dict[str, str]:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def install(self, app: str) -> None:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def uninstall(self, app: str) -> OperationResult:  # pragma: no cover
        raise NotImplementedError

    def uninstall_unmanaged(self, app: str) -> OperationResult:
        return self.uninstall(app)

    @abstractmethod
    def upgrade_all(self) -> None:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def find_unmanaged(self, managed: set[str]) -> list[UnmanagedApp]:  # pragma: no cover
        raise NotImplementedError


class BrewSourceService(BaseSourceService, ABC):
    """Shared Homebrew behavior for cask and formula strategies."""

    provider_name: ClassVar[str] = "brew"
    info_entries_key: ClassVar[str] = ""
    list_flag: ClassVar[str] = ""

    def _brew(self) -> str:
        return self.runner.get_executable("brew")

    def managed_aliases(self, app: str) -> set[str]:  # noqa: PLR6301
        return {app, app.rsplit("/", 1)[-1]}

    def list_installed(self) -> dict[str, str]:
        brew: str = self._brew()
        result = self.runner.run([brew, "list", self.list_flag])
        return {item: item for item in result.stdout.split()}

    def install(self, app: str) -> None:
        brew: str = self._brew()
        self.runner.run([brew, "install", self.list_flag, app])

    def uninstall(self, app: str) -> OperationResult:
        brew: str = self._brew()
        self.runner.run([brew, "uninstall", self.list_flag, app])
        return OperationResult.ok("")

    def upgrade_all(self) -> None:
        brew: str = self._brew()
        self.runner.run([brew, "update"], capture_output=False)
        self.runner.run([brew, "upgrade"], capture_output=False)
        self.runner.run([brew, "cleanup"], capture_output=False)

    def fetch_info(
        self, app: str, *, repo: AppsRepository, document: tomlkit.TOMLDocument
    ) -> AppInfo:
        del repo, document

        brew: str = self._brew()
        command: list[str] = [brew, "info", "--json=v2"]
        if self.source_name == "cask":
            command.append("--cask")
        command.append(app)

        result = self.runner.run(command)
        data: dict[str, list[dict[str, JSON]]] = json.loads(result.stdout)
        entries: list[dict[str, JSON]] = data.get(self.info_entries_key, [])
        if not entries:
            raise AppManagerError(f"No {self.info_entries_key} information returned for {app}.")

        entry: dict[str, JSON] = entries[0]
        description: JSON = entry.get("desc")
        if description is not None and not isinstance(description, str):
            description = str(description)

        website: str | None = None
        homepage: JSON = entry.get("homepage")
        if isinstance(homepage, str) and homepage.strip():
            website = homepage.strip()

        installed, version = self._extract_install_state(entry)

        return AppInfo(
            name=app,
            source=self.source_name,
            description=str(description) if description else None,
            website=website,
            version=version,
            installed=installed,
        )

    @staticmethod
    def _extract_install_state(entry: dict[str, JSON]) -> tuple[bool, str | None]:
        installed_field: JSON = entry.get("installed")
        version: str | None = None
        match installed_field:
            case list() if installed_field:
                first = installed_field[0]
                if isinstance(first, dict):
                    version = str(first.get("version")) if first.get("version") else None
                return True, version
            case str() as installed_version if installed_version:
                return True, installed_version

        versions: JSON = entry.get("versions")
        if isinstance(versions, dict):
            version_value: JSON = versions.get("stable") or versions.get("version")
            if isinstance(version_value, str):
                version = version_value

        return False, version


class BrewCaskSourceService(BrewSourceService):
    source_name = "cask"
    install_flag = "install_cask"
    sync_toggle_help = "Disable cask install/sync/upgrade"
    info_entries_key = "casks"
    list_flag = "--cask"

    def find_unmanaged(self, managed: set[str]) -> list[UnmanagedApp]:
        managed_norm: set[str] = {item.casefold() for item in managed}
        installed: dict[str, str] = self.list_installed()
        missing: list[UnmanagedApp] = []

        for app in sorted(installed):
            if app.casefold() in managed_norm:
                continue
            missing.append(UnmanagedApp(source=self.source_name, identifier=app, display=app))

        return missing

    def uninstall_unmanaged(self, app: str) -> OperationResult:
        brew: str = self._brew()
        self.runner.run([brew, "uninstall", "--cask", "--zap", app], capture_output=False)
        return OperationResult.ok("")


class BrewFormulaSourceService(BrewSourceService):
    source_name = "formula"
    install_flag = "install_formula"
    sync_toggle_help = "Disable formula install/sync/upgrade"
    info_entries_key = "formulae"
    list_flag = "--formula"

    def __init__(self, *, runner: CommandRunner, console: Console) -> None:
        super().__init__(runner=runner, console=console)
        self._linux_macos_only_cache: set[str] = set()

    def prime_linux_skip_cache(self, formulae: list[str]) -> None:
        if platform.system() == "Darwin":
            return
        self._linux_macos_only_cache = self.get_macos_only_formulas(formulae)

    def pre_install_check(self, app: str) -> OperationResult | None:
        if platform.system() == "Darwin":
            return None

        macos_only: set[str] = self._linux_macos_only_cache or self.get_macos_only_formulas([app])

        app_name: str = app.rsplit("/", 1)[-1]
        if app in macos_only or app_name in macos_only:
            return OperationResult.skipped_result(f"Skipping {app_name} (macOS only)")

        return None

    def find_unmanaged(self, managed: set[str]) -> list[UnmanagedApp]:
        managed_norm: set[str] = {item.casefold() for item in managed}
        brew: str = self._brew()
        leaves = self.runner.run([brew, "leaves"]).stdout.split()

        missing: list[UnmanagedApp] = []
        for app in sorted(leaves):
            if app.casefold() in managed_norm:
                continue
            missing.append(UnmanagedApp(source=self.source_name, identifier=app, display=app))

        return missing

    def get_macos_only_formulas(self, formula_list: list[str]) -> set[str]:
        if not formula_list:
            return set()

        brew: str = self._brew()
        command: list[str] = [brew, "info", "--json=v2", *formula_list]
        result = self.runner.run(command, check=False)

        try:
            data: dict[str, JSON] = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            return set()

        formulae: JSON = data.get("formulae")
        if not isinstance(formulae, list):
            return set()

        macos_only: set[str] = set()
        for entry in formulae:
            if isinstance(entry, dict):
                macos_only |= self._formula_entry_is_macos_only(entry)
        return macos_only

    @staticmethod
    def _formula_entry_is_macos_only(entry: dict[str, JSON]) -> set[str]:
        raw_requirements: JSON = entry.get("requirements")
        requirements: list[JSON] = raw_requirements if isinstance(raw_requirements, list) else []
        has_macos_requirement: bool = any(
            isinstance(requirement, dict) and requirement.get("name") == "macos"
            for requirement in requirements
        )
        if not has_macos_requirement:
            return set()

        bottle: JSON = entry.get("bottle")
        stable: JSON = bottle.get("stable") if isinstance(bottle, dict) else None
        files: JSON = stable.get("files") if isinstance(stable, dict) else {}
        if not isinstance(files, dict):
            return set()
        if any("linux" in str(key) for key in files):
            return set()

        names: set[str] = set()
        full_name: JSON = entry.get("full_name")
        name: JSON = entry.get("name")
        if isinstance(full_name, str):
            names.add(full_name)
        if isinstance(name, str):
            names.add(name)
        return names


class UvSourceService(BaseSourceService):
    source_name = "uv"
    install_flag = "install_uv"
    sync_toggle_help = "Disable uv install/sync/upgrade"

    def _uv(self) -> str:
        return self.runner.get_executable("uv")

    def fetch_info(
        self, app: str, *, repo: AppsRepository, document: tomlkit.TOMLDocument
    ) -> AppInfo:
        description: str | None = None
        record: AppRecord | None = repo.find_app(document, app)
        if record is not None and record.description:
            description = record.description

        installed: bool = False
        version: str | None = None
        for line in self.runner.run([self._uv(), "tool", "list"]).stdout.splitlines():
            stripped: str = line.strip()
            if not stripped or stripped.startswith("-"):
                continue
            parts: list[str] = stripped.split()
            if len(parts) < MIN_UV_LIST_COLUMNS:
                continue
            name, version_token = parts[0], parts[1]
            if name.casefold() == app.casefold() and version_token.startswith("v"):
                installed = True
                version = version_token
                break

        return AppInfo(
            name=app,
            source=self.source_name,
            description=description,
            website=f"https://pypi.org/project/{app}/",
            version=version,
            installed=installed,
        )

    def list_installed(self) -> dict[str, str]:
        result = self.runner.run([self._uv(), "tool", "list"])
        installed: dict[str, str] = {}
        for line in result.stdout.splitlines():
            stripped: str = line.strip()
            if not stripped or stripped.startswith("-"):
                continue
            name: str = stripped.split(maxsplit=1)[0]
            installed[name] = name
        return installed

    def install(self, app: str) -> None:
        self.runner.run([self._uv(), "tool", "install", app])

    def uninstall(self, app: str) -> OperationResult:
        self.runner.run([self._uv(), "tool", "uninstall", app])
        return OperationResult.ok("")

    def upgrade_all(self) -> None:
        self.runner.run([self._uv(), "tool", "upgrade", "--all"], capture_output=False)

    def find_unmanaged(self, managed: set[str]) -> list[UnmanagedApp]:
        managed_norm: set[str] = {item.casefold() for item in managed}
        installed: dict[str, str] = self.list_installed()
        missing: list[UnmanagedApp] = []
        for app in sorted(installed):
            if app.casefold() in managed_norm:
                continue
            missing.append(UnmanagedApp(source=self.source_name, identifier=app, display=app))
        return missing


class MasSourceService(BaseSourceService):
    source_name = "mas"
    install_flag = "install_mas"
    sync_toggle_help = "Disable mas install/sync/upgrade"

    def _mas(self) -> str:
        return self.runner.get_executable("mas")

    def fetch_info(
        self, app: str, *, repo: AppsRepository, document: tomlkit.TOMLDocument
    ) -> AppInfo:
        del repo, document

        result = self.runner.run([self._mas(), "info", app])

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
        description: str = description_line
        version: str | None = None
        if match:
            description = match.group("name").strip()
            version = match.group("version")

        installed_ids: set[str] = set(self.list_installed())

        return AppInfo(
            name=app,
            source=self.source_name,
            description=description,
            website=website,
            version=version,
            installed=app in installed_ids,
        )

    def list_installed(self) -> dict[str, str]:
        result = self.runner.run([self._mas(), "list"])
        apps: dict[str, str] = {}
        for line in result.stdout.splitlines():
            match = re.match(r"^(\d+)\s+(.+?)\s+\(.*\)$", line.strip())
            if not match:
                continue
            apps[match.group(1)] = match.group(2)
        return apps

    def install(self, app: str) -> None:
        self.runner.run([self._mas(), "install", app])

    def uninstall(self, app: str) -> OperationResult:
        result = self.runner.run(
            [self._mas(), "uninstall", app], check=False, capture_output=False
        )
        if result.returncode != 0:
            return OperationResult.failed(
                f"Failed to uninstall {app}. Please uninstall it manually."
            )
        return OperationResult.ok("")

    def upgrade_all(self) -> None:
        self.runner.run([self._mas(), "upgrade"], capture_output=False)

    def find_unmanaged(self, managed: set[str]) -> list[UnmanagedApp]:
        managed_norm: set[str] = {item.casefold() for item in managed}
        installed: dict[str, str] = self.list_installed()

        missing: list[UnmanagedApp] = []
        for app_id, app_name in sorted(installed.items()):
            if app_id.casefold() in managed_norm:
                continue
            missing.append(
                UnmanagedApp(
                    source=self.source_name,
                    identifier=app_id,
                    display=f"{app_name} ({app_id})",
                )
            )

        return missing


class AppManagerFacade:
    """Facade coordinating repository + strategies + command use cases."""

    def __init__(
        self,
        *,
        repository: AppsRepository,
        runner: CommandRunner,
        console: Console,
    ) -> None:
        self.repository = repository
        self.runner = runner
        self.console = console
        self._service_cache: dict[str, BaseSourceService] = {}

    def get_service(self, source: str) -> BaseSourceService:
        if source not in self._service_cache:
            self._service_cache[source] = SourceRegistry.create(
                source,
                runner=self.runner,
                console=self.console,
            )
        return self._service_cache[source]

    def add_app(
        self,
        *,
        app: str,
        source: str,
        group: str | None,
        description: str | None,
        no_install: bool,
    ) -> None:
        document = self.repository.load()
        selected_group: str = self._resolve_or_pick_group(document, group)
        final_description: str = self._infer_description(
            source=source,
            app=app,
            description=description,
            document=document,
        )

        outcome: AddAppOutcome = self.repository.add_or_update(
            document,
            app=app,
            source=source,
            group=selected_group,
            description=final_description,
        )

        if outcome.moved_from is not None:
            move_message: str = (
                f"Moved {outcome.app_key!r} from [{outcome.moved_from}] to "
                f'[{outcome.group}] with source "{source}" '
                f'and description "{outcome.description}".'
            )
            self.console.paint(move_message, Ansi.CYAN, icon="➡️")
        elif outcome.existed:
            self.console.paint(
                f"Updated {outcome.app_key!r} in [{outcome.group}] with source '{source}' "
                f'and description "{outcome.description}".',
                Ansi.CYAN,
                icon="🔄",
            )
        else:
            self.console.paint(
                f"Added {outcome.app_key!r} to [{outcome.group}] with source '{source}' "
                f'and description "{outcome.description}".',
                Ansi.GREEN,
                icon="✅",
            )

        if no_install:
            self.repository.save(document)
            return

        failure_message: str | None = None
        try:
            if outcome.previous_source and outcome.previous_source != source:
                uninstall_result: OperationResult = self.get_service(
                    outcome.previous_source
                ).ensure_uninstalled(outcome.app_key)
                self.console.emit_operation(uninstall_result, success_style=Ansi.MAGENTA)
                if not uninstall_result.success:
                    failure_message = uninstall_result.message

            install_result: OperationResult = self.get_service(source).ensure_installed(
                outcome.app_key
            )
            self.console.emit_operation(install_result)
            if not install_result.success:
                failure_message = install_result.message
        except AppManagerError as error:
            failure_message = str(error)

        if failure_message:
            self.console.paint(
                f"Install failed; rolling back apps.toml changes for {outcome.app_key!r}.",
                Ansi.YELLOW,
                icon="↩️",
            )
            raise AppManagerError(failure_message)

        self.repository.save(document)

    def remove_app(self, *, app: str, no_install: bool) -> None:
        document = self.repository.load()
        outcome: RemoveAppOutcome = self.repository.remove(document, app)

        if not outcome.removed:
            self.console.paint(f"{app!r} not found in apps.toml.", Ansi.YELLOW, icon="⚠️")
            return

        if outcome.app_key is None or outcome.group is None:
            raise AppManagerError("Removal failed due to inconsistent app state.")
        self.console.paint(
            f"Removed {outcome.app_key!r} from [{outcome.group}].",
            Ansi.MAGENTA,
            icon="🗑️",
        )

        self.repository.save(document)

        if no_install:
            return

        if outcome.source is None:
            raise AppManagerError("Removal failed because the source is unknown.")
        uninstall_result: OperationResult = self.get_service(outcome.source).ensure_uninstalled(
            outcome.app_key
        )
        self.console.emit_operation(uninstall_result, success_style=Ansi.MAGENTA)

    def list_apps(self) -> None:
        document = self.repository.load()
        self.console.render_records(self.repository.list_grouped_records(document))

    def print_info(self, *, app: str, source: str) -> None:
        document = self.repository.load()
        info: AppInfo = self.get_service(source).fetch_info(
            app, repo=self.repository, document=document
        )
        self.console.print_info(info)

    def sync_apps(self, options: SyncOptions) -> None:
        document = self.repository.load()

        self.console.paint("Installing apps and packages...", Ansi.BLUE, icon="📲")
        enabled: list[str] = sorted(options.enabled_sources)
        self.console.paint(
            f"Sources: {' '.join(enabled) if enabled else 'none'}",
            Ansi.BLUE,
            icon="📋",
        )

        grouped_records: list[tuple[str, list[AppRecord]]] = self.repository.list_grouped_records(
            document
        )
        self._prime_source_caches(grouped_records, options)
        self._install_declared(grouped_records, options)

        self.console.paint(
            "Syncing installed apps to apps.toml...",
            Ansi.MAGENTA,
            icon="🔄",
            newline=True,
        )
        self._sync_unmanaged(grouped_records, options)

        self.console.paint(
            "Updating existing apps and packages...", Ansi.MAGENTA, icon="🔼", newline=True
        )
        self._upgrade_sources(options)

    def _resolve_or_pick_group(
        self,
        document: tomlkit.TOMLDocument,
        group: str | None,
    ) -> str:
        if group:
            return self.repository.resolve_group_name(document, group)
        return self.pick_group_interactively(document)

    def pick_group_interactively(self, document: tomlkit.TOMLDocument) -> str:
        def prompt_non_empty(prompt: str) -> str:
            while True:
                try:
                    value: str = input(prompt).strip()
                except (EOFError, KeyboardInterrupt) as exc:
                    print()
                    raise AppManagerError("No group selected.") from exc
                if value:
                    return value
                self.console.paint("Group name cannot be empty.", Ansi.YELLOW, icon="⚠️")

        groups: list[str] = [group for group, _ in self.repository.iter_group_tables(document)]
        if not sys.stdin.isatty():
            raise AppManagerError(
                "No --group/-g provided and stdin is not interactive. Provide --group explicitly."
            )

        if not groups:
            return self.repository.resolve_group_name(
                document, prompt_non_empty("New group name: ")
            )

        self.console.paint(
            "No group provided. Select which group to add the app to:",
            Ansi.CYAN,
            newline=True,
        )
        self.console.paint(" 0. <create a new group>", bold=False)
        self.console.paint(
            "\n".join(f"{index:>2}. {name}" for index, name in enumerate(groups, start=1)),
            bold=False,
        )

        by_norm: dict[str, str] = {self.repository.normalize_key(name): name for name in groups}

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
                    return self.repository.resolve_group_name(
                        document,
                        prompt_non_empty("New group name: "),
                    )
                if 1 <= index <= len(groups):
                    return groups[index - 1]
                self.console.paint("Invalid selection. Try again.", Ansi.YELLOW, icon="⚠️")
                continue

            existing: str | None = by_norm.get(self.repository.normalize_key(choice))
            if existing is not None:
                return existing

            return self.repository.resolve_group_name(document, choice)

    def _infer_description(
        self,
        *,
        source: str,
        app: str,
        description: str | None,
        document: tomlkit.TOMLDocument,
    ) -> str:
        normalized: str | None = description.strip() if description is not None else None

        if source == "uv" and not normalized:
            raise AppManagerError(
                "Description is required for uv-installed apps. Use --description/-d."
            )

        if normalized:
            return normalized

        info: AppInfo = self.get_service(source).fetch_info(
            app, repo=self.repository, document=document
        )
        if info.description:
            return info.description

        raise AppManagerError(
            f"Could not determine description for {app}. Provide --description explicitly."
        )

    def _prime_source_caches(
        self,
        grouped_records: list[tuple[str, list[AppRecord]]],
        options: SyncOptions,
    ) -> None:
        if "formula" not in options.enabled_sources:
            return
        formula_service = self.get_service("formula")
        if not isinstance(formula_service, BrewFormulaSourceService):
            return

        formula_list: list[str] = [
            record.key
            for _, records in grouped_records
            for record in records
            if record.source == "formula"
        ]
        formula_service.prime_linux_skip_cache(formula_list)

    def _install_declared(
        self,
        grouped_records: list[tuple[str, list[AppRecord]]],
        options: SyncOptions,
    ) -> None:
        current_group: str | None = None
        for group, records in grouped_records:
            for record in records:
                if record.source not in options.enabled_sources:
                    continue

                if group != current_group:
                    suffix = "" if group.endswith("s") else " apps"
                    self.console.paint(
                        f"Installing {group}{suffix}...",
                        Ansi.MAGENTA,
                        icon="📦",
                        newline=True,
                    )
                    current_group = group

                result: OperationResult = self.get_service(record.source).ensure_installed(
                    record.key
                )
                if result.skipped and "Skipping" in result.message:
                    self.console.paint(result.message, Ansi.RED, icon="⏭️")
                else:
                    self.console.emit_operation(result)

    def _sync_unmanaged(
        self,
        grouped_records: list[tuple[str, list[AppRecord]]],
        options: SyncOptions,
    ) -> None:
        enabled: set[str] = options.enabled_sources
        records: list[AppRecord] = [record for _, rows in grouped_records for record in rows]

        provider_to_sources: dict[str, list[str]] = {}
        for source in enabled:
            provider_to_sources.setdefault(self.get_service(source).maintenance_key, []).append(
                source
            )

        for provider, provider_sources in sorted(provider_to_sources.items()):
            managed: set[str] = set()
            for source in provider_sources:
                service = self.get_service(source)
                for record in records:
                    if record.source != source:
                        continue
                    managed |= service.managed_aliases(record.key)

            unmanaged: list[UnmanagedApp] = []
            for source in provider_sources:
                unmanaged.extend(self.get_service(source).find_unmanaged(managed))

            header, ok_message = self._provider_sync_messages(provider)
            if not unmanaged:
                self.console.paint(ok_message, Ansi.GREEN, icon="✅")
                continue

            items: list[str] = [item.display for item in unmanaged]
            self.console.print_missing(header, items)
            if not self.console.prompt_yes_no(
                "Do you want to uninstall these apps? (y/n) ",
                auto_yes=options.yes,
            ):
                self.console.paint("No apps were uninstalled.", Ansi.MAGENTA, icon="🆗")
                continue

            for item in unmanaged:
                self.console.paint(f"Uninstalling {item.display}...", Ansi.MAGENTA, icon="🗑️")
                result: OperationResult = self.get_service(item.source).uninstall_unmanaged(
                    item.identifier
                )
                if not result.success:
                    self.console.paint(result.message, Ansi.RED, icon="❌")
                    continue
                self.console.paint(f"Uninstalled {item.display}.", Ansi.MAGENTA, icon="🚮")

    @staticmethod
    def _provider_sync_messages(provider: str) -> tuple[str, str]:
        match provider:
            case "brew":
                return (
                    (
                        "The following Homebrew-installed formulae and casks are missing from "
                        "apps.toml:"
                    ),
                    "All Homebrew-installed formulae and casks are present in apps.toml.",
                )
            case "uv":
                return (
                    "The following uv-installed apps are missing from apps.toml:",
                    "All uv-installed apps are present in apps.toml.",
                )
            case "mas":
                return (
                    "The following Mac App Store apps are missing from apps.toml:",
                    "All Mac App Store apps are present in apps.toml.",
                )
            case _:
                return (
                    f"The following {provider}-installed apps are missing from apps.toml:",
                    f"All {provider}-installed apps are present in apps.toml.",
                )

    def _upgrade_sources(self, options: SyncOptions) -> None:
        seen: set[str] = set()
        for source in sorted(options.enabled_sources):
            service = self.get_service(source)
            key: str = service.maintenance_key
            if key in seen:
                continue
            service.upgrade_all()
            seen.add(key)


class BaseCommand(ABC):
    """Command pattern interface for each CLI subcommand."""

    command_name: ClassVar[str]

    def __init__(self, *, facade: AppManagerFacade) -> None:
        self.facade = facade

    @abstractmethod
    def execute(self, args: argparse.Namespace) -> None:  # pragma: no cover
        raise NotImplementedError


class AddAppCommand(BaseCommand):
    command_name = "add"

    def execute(self, args: argparse.Namespace) -> None:
        self.facade.add_app(
            app=args.app,
            source=args.source,
            group=args.group,
            description=args.description,
            no_install=args.no_install,
        )


class RemoveAppCommand(BaseCommand):
    command_name = "remove"

    def execute(self, args: argparse.Namespace) -> None:
        self.facade.remove_app(app=args.app, no_install=args.no_install)


class ListAppsCommand(BaseCommand):
    command_name = "list"

    def execute(self, args: argparse.Namespace) -> None:
        del args
        self.facade.list_apps()


class InfoAppCommand(BaseCommand):
    command_name = "info"

    def execute(self, args: argparse.Namespace) -> None:
        self.facade.print_info(app=args.app, source=args.source)


class SyncAppsCommand(BaseCommand):
    command_name = "sync"

    def execute(self, args: argparse.Namespace) -> None:
        enabled: set[str] = {
            config.name
            for config in SourceRegistry.source_configs()
            if bool(getattr(args, config.install_flag, False))
        }
        options = SyncOptions(yes=args.yes, enabled_sources=enabled)
        self.facade.sync_apps(options)


class CommandDispatcher:
    """Maps parsed command names to command handlers."""

    def __init__(self, *, facade: AppManagerFacade) -> None:
        self._commands: dict[str, BaseCommand] = {
            AddAppCommand.command_name: AddAppCommand(facade=facade),
            RemoveAppCommand.command_name: RemoveAppCommand(facade=facade),
            ListAppsCommand.command_name: ListAppsCommand(facade=facade),
            InfoAppCommand.command_name: InfoAppCommand(facade=facade),
            SyncAppsCommand.command_name: SyncAppsCommand(facade=facade),
        }

    def dispatch(self, args: argparse.Namespace) -> None:
        command = self._commands.get(args.command)
        if command is None:
            raise AppManagerError(f"Unknown command: {args.command!r}")
        command.execute(args)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed CLI arguments.

    Raises:
        AppManagerError: If no source strategies are registered.
    """
    parser = argparse.ArgumentParser(description="Manage and install applications using apps.toml")
    parser.add_argument(
        "--apps-file",
        default=APPS_TOML,
        type=Path,
        help=f"Path to apps.toml (default: {APPS_TOML})",
    )

    source_names: list[str] = SourceRegistry.source_names()
    if not source_names:
        raise AppManagerError("No sources are registered.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add an app to apps.toml and install it")
    add_parser.add_argument("app", help="App name or identifier")
    add_parser.add_argument(
        "source",
        choices=source_names,
        help=f"Source of the app (choices: {', '.join(source_names)})",
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
            "Description for the app. Required for 'uv' sources; optional overrides for other "
            "sources."
        ),
    )
    add_parser.add_argument(
        "--no-install",
        action="store_true",
        help="Skip installing or uninstalling apps and only update the apps.toml file",
    )

    remove_parser = subparsers.add_parser(
        "remove",
        help="Remove an app from apps.toml and uninstall it",
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
        "-y", "--yes", action="store_true", help="Auto-confirm uninstall prompts"
    )

    for config in SourceRegistry.source_configs():
        sync_parser.add_argument(
            f"--no-{config.name}",
            action="store_false",
            dest=config.install_flag,
            default=True,
            help=config.sync_help,
        )

    info_parser = subparsers.add_parser("info", help="Show app details")
    info_parser.add_argument("app", help="App name or identifier")
    info_parser.add_argument(
        "source",
        choices=source_names,
        help=f"Source of the app (choices: {', '.join(source_names)})",
    )

    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""
    args: argparse.Namespace = parse_args()
    console = Console()
    runner = CommandRunner()
    repository = AppsRepository(args.apps_file, console=console)
    facade = AppManagerFacade(repository=repository, runner=runner, console=console)
    dispatcher = CommandDispatcher(facade=facade)
    dispatcher.dispatch(args)


if __name__ == "__main__":
    try:
        main()
    except AppManagerError as error:
        raise SystemExit(f"❌ {error}") from None
    except KeyboardInterrupt:
        raise SystemExit("\n❌ Operation cancelled by user.") from None
