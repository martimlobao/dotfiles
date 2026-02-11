from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest
import tomlkit

SPEC = importlib.util.spec_from_file_location("app_module", Path("scripts/app.py"))
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("failed to load scripts/app.py")
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)
app_module: ModuleType = app


def test_parse_args_add_command() -> None:
    argv = ["app", "add", "httpie", "uv", "--group", "cli", "--description", "desc"]
    with patch.object(sys, "argv", argv):
        args = app_module.parse_args()
    assert args.command == "add"
    assert args.app == "httpie"
    assert args.source == "uv"
    assert args.group == "cli"


def test_parse_args_sync_flags() -> None:
    argv = ["app", "sync", "--no-cask", "--no-formula"]
    with patch.object(sys, "argv", argv):
        args = app_module.parse_args()
    assert args.command == "sync"
    assert not args.install_cask
    assert not args.install_formula
    assert args.install_uv
    assert args.install_mas


def test_resolve_group_name_case_insensitive() -> None:
    document = tomlkit.parse('[CLI-Tools]\nhttpie = "uv"\n')
    assert app_module.resolve_group_name(document, "cli-tools") == "CLI-Tools"


def test_validate_duplicates_across_groups() -> None:
    document = tomlkit.parse('[one]\nfoo = "uv"\n[two]\nFoo = "cask"\n')
    with pytest.raises(app_module.AppManagerError, match="Duplicate apps found"):
        app_module.validate_no_duplicate_apps(document, apps_file=Path("apps.toml"))


def test_load_apps_creates_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "apps.toml"
    document = app_module.load_apps(path)
    assert path.exists()
    assert list(document.items()) == []


def test_find_app_group_case_insensitive() -> None:
    document = tomlkit.parse('[dev]\nHTTPie = "uv"\n')
    assert app_module.find_app_group(document, "httpie") == ("HTTPie", "uv", "dev")


def test_add_app_updates_existing_and_moves_group() -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\n')
    args = argparse.Namespace(
        app="foo",
        source="cask",
        group="tools",
        description="new",
        no_install=True,
    )
    changed, previous = app_module.add_app(document, args)
    assert changed
    assert previous == "formula"
    assert "tools" in document
    assert "dev" not in document


def test_remove_app_returns_source() -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\n')
    removed, source = app_module.remove_app(document, "foo")
    assert removed
    assert source == "formula"


def test_infer_description_requires_uv_description() -> None:
    with pytest.raises(app_module.AppManagerError):
        app_module.infer_description("uv", "httpie", None, tomlkit.document())


def test_install_app_skips_when_already_installed() -> None:
    with (
        patch.object(app_module, "fetch_app_info") as fetch_info,
        patch.object(app_module, "_run") as run,
    ):
        fetch_info.return_value = app_module.AppInfo(
            name="foo",
            source="formula",
            description=None,
            website=None,
            version=None,
            installed=True,
        )
        app_module.install_app(tomlkit.document(), source="formula", app="foo")
        run.assert_not_called()


def test_install_app_runs_command() -> None:
    with (
        patch.object(app_module, "fetch_app_info") as fetch_info,
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(app_module, "_run") as run,
    ):
        fetch_info.return_value = app_module.AppInfo(
            name="foo",
            source="formula",
            description=None,
            website=None,
            version=None,
            installed=False,
        )
        app_module.install_app(tomlkit.document(), source="formula", app="foo")
        run.assert_called_once_with(["brew", "install", "--formula", "foo"])


def test_uninstall_app_runs_command() -> None:
    with (
        patch.object(app_module, "fetch_app_info") as fetch_info,
        patch.object(app_module, "_get_executable", return_value="uv"),
        patch.object(app_module, "_run") as run,
    ):
        fetch_info.return_value = app_module.AppInfo(
            name="foo",
            source="uv",
            description=None,
            website=None,
            version=None,
            installed=True,
        )
        app_module.uninstall_app(tomlkit.document(), source="uv", app="foo")
        run.assert_called_once_with(["uv", "tool", "uninstall", "foo"])


def test_list_apps_empty(capsys: pytest.CaptureFixture[str]) -> None:
    app_module.list_apps(tomlkit.document())
    output = capsys.readouterr().out
    assert "No apps found." in output


def test_print_app_info(capsys: pytest.CaptureFixture[str]) -> None:
    info = app_module.AppInfo(
        name="httpie",
        source="uv",
        description="cli",
        website="https://pypi.org/project/httpie/",
        version="v1.0.0",
        installed=True,
    )
    app_module.print_app_info(info)
    output = capsys.readouterr().out
    assert "Name" in output
    assert "httpie" in output


def test_fetch_app_info_unknown_source_raises() -> None:
    with pytest.raises(app_module.AppManagerError, match="Unknown source"):
        app_module.fetch_app_info("unknown", "foo", tomlkit.document())


def test_sync_apps_orchestrates_all_steps() -> None:
    with (
        patch.object(
            app_module,
            "_iter_apps_by_source",
            return_value={"cask": [], "formula": [], "uv": [], "mas": []},
        ),
        patch.object(app_module, "_build_installed_state"),
        patch.object(app_module, "_install_declared_apps") as install_declared,
        patch.object(app_module, "_sync_homebrew") as sync_homebrew,
        patch.object(app_module, "_sync_uv") as sync_uv,
        patch.object(app_module, "_sync_mas") as sync_mas,
        patch.object(app_module, "_update_and_cleanup") as cleanup,
    ):
        args = SimpleNamespace(
            install_cask=True,
            install_formula=True,
            install_uv=True,
            install_mas=True,
        )
        app_module.sync_apps(tomlkit.document(), args)
        install_declared.assert_called_once()
        sync_homebrew.assert_called_once()
        sync_uv.assert_called_once()
        sync_mas.assert_called_once()
        cleanup.assert_called_once()
