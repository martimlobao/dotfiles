# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "pytest>=9.0.2",
#     "pytest-cov>=7.0.0",
#     "tomlkit>=0.14.0",
# ]
# [tool.uv]
# exclude-newer = "2026-02-12T00:00:00Z"
# ///
from __future__ import annotations

import argparse
import builtins
import importlib.util
import json
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


def test_add_app_updates_in_place(capsys: pytest.CaptureFixture[str]) -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"  # old\n')
    args = argparse.Namespace(
        app="foo",
        source="cask",
        group="dev",
        description="new desc",
        no_install=True,
    )
    with patch.object(
        app_module,
        "fetch_app_info",
        return_value=app_module.AppInfo(
            name="foo",
            source="formula",
            description="old",
            website=None,
            version=None,
            installed=False,
        ),
    ):
        changed, previous = app_module.add_app(document, args)
    assert changed
    assert previous == "formula"
    assert "Updated" in capsys.readouterr().out


def test_add_app_raise_when_remove_fails() -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\n[tools]\nbar = "cask"\n')
    args = argparse.Namespace(
        app="foo",
        source="cask",
        group="tools",
        description="desc",
        no_install=True,
    )
    with (
        patch.object(
            app_module,
            "remove_app_from_group",
            return_value=False,
        ),
        pytest.raises(app_module.AppManagerError, match="could not be removed"),
    ):
        app_module.add_app(document, args)


def test_add_app_new_group() -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\n')
    args = argparse.Namespace(
        app="bar",
        source="cask",
        group="tools",
        description="new",
        no_install=True,
    )
    changed, previous = app_module.add_app(document, args)
    assert not changed
    assert previous is None
    assert "tools" in document
    assert document["tools"]["bar"] == "cask"


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
        patch.object(app_module, "platform") as platform_mock,
    ):
        platform_mock.system.return_value = "Darwin"
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


def test_uninstall_app_skips_when_not_installed(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch.object(app_module, "fetch_app_info") as fetch_info,
        patch.object(app_module, "_run") as run,
    ):
        fetch_info.return_value = app_module.AppInfo(
            name="foo",
            source="uv",
            description=None,
            website=None,
            version=None,
            installed=False,
        )
        app_module.uninstall_app(tomlkit.document(), source="uv", app="foo")
        run.assert_not_called()
        output = capsys.readouterr().out
        assert "skipping uninstall" in output


def test_install_app_unknown_source_raises() -> None:
    with pytest.raises(app_module.AppManagerError, match="Unknown source"):
        app_module.install_app(tomlkit.document(), source="unknown", app="foo")


def test_uninstall_app_unknown_source_raises() -> None:
    with pytest.raises(app_module.AppManagerError, match="Unknown source"):
        app_module.uninstall_app(tomlkit.document(), source="unknown", app="foo")


def test_package_command_unknown_source_raises() -> None:
    with pytest.raises(app_module.AppManagerError, match="Unknown source"):
        app_module._package_command(source="invalid", app="foo", install=True)


def test_install_from_source_unknown_source_raises() -> None:
    state = app_module.InstalledState(casks=set(), formulas=set(), uv=set(), mas={})
    with pytest.raises(app_module.AppManagerError, match="Unknown installation source"):
        app_module._install_from_source(
            app="foo",
            source="bad_source",
            state=state,
        )


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


def test_fetch_app_info_cask() -> None:
    brew_json = json.dumps({"casks": [{"desc": "x", "homepage": "", "installed": "1"}]})
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout=brew_json, returncode=0),
        ),
    ):
        info = app_module.fetch_app_info("cask", "chrome", tomlkit.document())
    assert info.source == "cask"


def test_fetch_app_info_uv() -> None:
    with (
        patch.object(app_module, "_get_executable", return_value="uv"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout="foo  v1.0\n", returncode=0),
        ),
    ):
        info = app_module.fetch_app_info("uv", "foo", tomlkit.document())
    assert info.source == "uv"


def test_fetch_app_info_mas() -> None:
    with (
        patch.object(app_module, "_get_executable", return_value="mas"),
        patch.object(
            app_module,
            "_run",
            side_effect=[
                SimpleNamespace(stdout="App 1.0\n", returncode=0),
                SimpleNamespace(stdout="123 App (1.0)\n", returncode=0),
            ],
        ),
    ):
        info = app_module.fetch_app_info("mas", "123", tomlkit.document())
    assert info.source == "mas"


def test_fetch_app_info_unknown_source_raises() -> None:
    with pytest.raises(app_module.AppManagerError, match="Unknown source"):
        app_module.fetch_app_info("unknown", "foo", tomlkit.document())


def test_fetch_brew_info_cask() -> None:
    brew_json = json.dumps({
        "casks": [
            {
                "desc": "Browser",
                "homepage": "https://example.com",
                "installed": "1.0",
            }
        ],
    })
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout=brew_json, returncode=0),
        ),
    ):
        info = app_module.fetch_brew_info("chrome", "cask")
    assert info.name == "chrome"
    assert info.source == "cask"
    assert info.description == "Browser"
    assert info.installed
    assert info.version == "1.0"


def test_fetch_brew_info_formula() -> None:
    brew_json = json.dumps({
        "formulae": [
            {
                "desc": "GitHub CLI",
                "homepage": "https://cli.github.com",
                "installed": [{"version": "2.0"}],
            }
        ],
    })
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout=brew_json, returncode=0),
        ),
    ):
        info = app_module.fetch_brew_info("gh", "formula")
    assert info.name == "gh"
    assert info.source == "formula"
    assert info.installed


def test_fetch_brew_info_uninstalled_with_versions() -> None:
    brew_json = json.dumps({
        "formulae": [
            {
                "desc": "CLI",
                "homepage": "https://example.com",
                "versions": {"stable": "2.0"},
            }
        ],
    })
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout=brew_json, returncode=0),
        ),
    ):
        info = app_module.fetch_brew_info("gh", "formula")
    assert not info.installed
    assert info.version == "2.0"


def test_fetch_brew_info_not_found_raises() -> None:
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout=json.dumps({"casks": []}), returncode=0),
        ),
        pytest.raises(app_module.AppManagerError, match="No casks"),
    ):
        app_module.fetch_brew_info("nonexistent", "cask")


def test_fetch_mas_info() -> None:
    mas_info = "Numbers  1.0 [foo]\nFrom: https://example.com\n"
    mas_list = "409203825 Numbers (1.0)\n"
    with (
        patch.object(app_module, "_get_executable", return_value="mas"),
        patch.object(
            app_module,
            "_run",
            side_effect=[
                SimpleNamespace(stdout=mas_info, returncode=0),
                SimpleNamespace(stdout=mas_list, returncode=0),
            ],
        ),
    ):
        info = app_module.fetch_mas_info("409203825")
    assert info.name == "409203825"
    assert info.source == "mas"
    assert info.installed
    assert info.description == "Numbers"
    assert info.website == "https://example.com"


def test_fetch_uv_info() -> None:
    with (
        patch.object(app_module, "_get_executable", return_value="uv"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(
                stdout="httpie  v1.0.0\nother  v2.0\n",
                returncode=0,
            ),
        ),
    ):
        info = app_module.fetch_uv_info(tomlkit.document(), "httpie")
    assert info.name == "httpie"
    assert info.installed
    assert info.version == "v1.0.0"


def test_fetch_uv_info_from_document() -> None:
    document = tomlkit.parse('[cli]\nhttpie = "uv"  # HTTP client\n')
    with (
        patch.object(app_module, "_get_executable", return_value="uv"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout="other  v1.0\n", returncode=0),
        ),
    ):
        info = app_module.fetch_uv_info(document, "httpie")
    assert info.description == "HTTP client"


def test_list_apps_with_groups(capsys: pytest.CaptureFixture[str]) -> None:
    document = tomlkit.parse(
        '[cli]\nhttpie = "uv"  # HTTP client\n[dev]\ngh = "formula"  # GitHub CLI\n'
    )
    app_module.list_apps(document)
    output = capsys.readouterr().out
    assert "httpie" in output
    assert "gh" in output
    assert "cli" in output
    assert "dev" in output
    assert "uv" in output or "formula" in output


def test_list_apps_no_groups(capsys: pytest.CaptureFixture[str]) -> None:
    document = tomlkit.parse("[empty]\n")
    app_module.list_apps(document)
    output = capsys.readouterr().out
    assert "No apps found" in output


def test_remove_app_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\n')
    removed, source = app_module.remove_app(document, "bar")
    assert not removed
    assert source is None
    assert "not found" in capsys.readouterr().out


def test_load_apps_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "apps.toml"
    path.write_text('[dev]\nfoo = "formula"\n')
    document = app_module.load_apps(path)
    assert "dev" in document
    assert document["dev"]["foo"] == "formula"


def test_save_apps(tmp_path: Path) -> None:
    path = tmp_path / "apps.toml"
    document = tomlkit.parse('[dev]\nfoo = "formula"\n')
    app_module.save_apps(path, document)
    assert path.read_text() == '[dev]\nfoo = "formula"\n'


def test_resolve_group_name_empty_raises() -> None:
    document = tomlkit.document()
    with pytest.raises(app_module.AppManagerError, match="cannot be empty"):
        app_module.resolve_group_name(document, "   ")


def test_pick_group_interactively_select_by_number() -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\n[tools]\nbar = "cask"\n')
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=True),
        patch.object(builtins, "input", side_effect=["1"]),
    ):
        result = app_module.pick_group_interactively(document)
    assert result == "dev"


def test_pick_group_interactively_select_new_group() -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\n')
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=True),
        patch.object(builtins, "input", side_effect=["0", "newgroup"]),
    ):
        result = app_module.pick_group_interactively(document)
    assert result == "newgroup"


def test_pick_group_interactively_empty_file() -> None:
    document = tomlkit.document()
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=True),
        patch.object(builtins, "input", return_value="first"),
    ):
        result = app_module.pick_group_interactively(document)
    assert result == "first"


def test_pick_group_interactively_select_by_name() -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\n[tools]\nbar = "cask"\n')
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=True),
        patch.object(builtins, "input", return_value="tools"),
    ):
        result = app_module.pick_group_interactively(document)
    assert result == "tools"


def test_pick_group_interactively_new_group_by_name() -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\n')
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=True),
        patch.object(builtins, "input", return_value="mygroup"),
    ):
        result = app_module.pick_group_interactively(document)
    assert result == "mygroup"


def test_pick_group_interactively_invalid_number_retries() -> None:
    document = tomlkit.parse("[dev]\n[tools]\n")
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=True),
        patch.object(builtins, "input", side_effect=["99", "1"]),
    ):
        result = app_module.pick_group_interactively(document)
    assert result == "dev"


def test_pick_group_interactively_not_tty_raises() -> None:
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=False),
        pytest.raises(app_module.AppManagerError, match="not interactive"),
    ):
        app_module.pick_group_interactively(tomlkit.document())


def test_resolve_group_name_normalizes_to_existing() -> None:
    document = tomlkit.parse('[Dev-Tools]\nfoo = "formula"\n')
    assert app_module.resolve_group_name(document, "dev-tools") == "Dev-Tools"


def test_validate_duplicates_same_group_allowed() -> None:
    document = tomlkit.parse('[one]\nfoo = "uv"\nbar = "cask"\n')
    app_module.validate_no_duplicate_apps(document, apps_file=Path("apps.toml"))


def test_remove_app_from_group_removes_section_when_empty() -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\n')
    removed = app_module.remove_app_from_group(document, group="dev", app_key="foo")
    assert removed
    assert "dev" not in document


def test_remove_app_from_group_key_not_in_table() -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\n')
    removed = app_module.remove_app_from_group(document, group="dev", app_key="bar")
    assert not removed


def test_remove_app_from_group_group_not_table() -> None:
    document = tomlkit.document()
    document["dev"] = "not a table"
    removed = app_module.remove_app_from_group(document, group="dev", app_key="foo")
    assert not removed


def test_remove_app_from_group_keeps_section_with_others() -> None:
    document = tomlkit.parse('[dev]\nfoo = "formula"\nbar = "cask"\n')
    removed = app_module.remove_app_from_group(document, group="dev", app_key="foo")
    assert removed
    assert "dev" in document
    assert "bar" in document["dev"]


def test_install_from_source_already_installed_cask(capsys: pytest.CaptureFixture[str]) -> None:
    state = app_module.InstalledState(
        casks={"chromedriver"},
        formulas=set(),
        uv=set(),
        mas={},
    )
    with patch.object(app_module, "_run") as run:
        app_module._install_from_source(
            app="chromedriver",
            source="cask",
            state=state,
        )
        run.assert_not_called()
    assert "already installed" in capsys.readouterr().out


def test_install_from_source_installs_cask() -> None:
    state = app_module.InstalledState(casks=set(), formulas=set(), uv=set(), mas={})
    with (
        patch.object(app_module, "_get_executable", return_value="/opt/homebrew/bin/brew"),
        patch.object(app_module, "_run") as run,
    ):
        app_module._install_from_source(
            app="chromedriver",
            source="cask",
            state=state,
        )
        run.assert_called_once()
        call_args = run.call_args[0][0]
        assert "brew" in call_args[0] or call_args[0] == "/opt/homebrew/bin/brew"
        assert "install" in call_args
        assert "--cask" in call_args
        assert "chromedriver" in call_args


def test_install_from_source_installs_formula() -> None:
    state = app_module.InstalledState(casks=set(), formulas=set(), uv=set(), mas={})
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(app_module, "_run") as run,
    ):
        app_module._install_from_source(
            app="gh",
            source="formula",
            state=state,
        )
        run.assert_called_once()
        call_args = run.call_args[0][0]
        assert "install" in call_args
        assert "--formula" in call_args


def test_install_from_source_installs_uv() -> None:
    state = app_module.InstalledState(casks=set(), formulas=set(), uv=set(), mas={})
    with (
        patch.object(app_module, "_get_executable", return_value="uv"),
        patch.object(app_module, "_run") as run,
    ):
        app_module._install_from_source(
            app="httpie",
            source="uv",
            state=state,
        )
        run.assert_called_once()
        call_args = run.call_args[0][0]
        assert "uv" in call_args[0].lower() or "tool" in call_args
        assert "install" in call_args
        assert "httpie" in call_args


def test_install_from_source_installs_mas() -> None:
    state = app_module.InstalledState(casks=set(), formulas=set(), uv=set(), mas={})
    with (
        patch.object(app_module, "_get_executable", return_value="mas"),
        patch.object(app_module, "_run") as run,
    ):
        app_module._install_from_source(
            app="409203825",
            source="mas",
            state=state,
        )
        run.assert_called_once()
        call_args = run.call_args[0][0]
        assert "install" in call_args or "mas" in call_args[0].lower()


def test_paint_with_style_when_tty(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(app_module.sys.stdout, "isatty", return_value=True):
        result = app_module.paint("hello", app_module.Ansi.GREEN, print_it=True)
    output = capsys.readouterr().out
    assert "hello" in output
    assert result  # contains ANSI codes when TTY


def test_paint_returns_string_when_print_it_false() -> None:
    result = app_module.paint("hello", app_module.Ansi.GREEN, print_it=False)
    assert "hello" in result


def test_paint_with_icon(capsys: pytest.CaptureFixture[str]) -> None:
    app_module.paint("msg", app_module.Ansi.RED, icon="❌")
    output = capsys.readouterr().out
    assert "❌" in output
    assert "msg" in output


def test_truncate() -> None:
    assert app_module._truncate("hello", 3) == "he…"
    assert app_module._truncate("hi", 10) == "hi"
    assert app_module._truncate("x", 1) == "x"


def test_visible_len_strips_ansi() -> None:
    colored = "\x1b[31mred\x1b[0m"
    assert app_module._visible_len(colored) == 3


def test_ljust_ansi_pads_correctly() -> None:
    colored = "\x1b[1mab\x1b[0m"
    result = app_module._ljust_ansi(colored, 5)
    assert app_module._visible_len(result) == 5


def test_get_executable_raises_when_not_found() -> None:
    with (
        patch.object(app_module.shutil, "which", return_value=None),
        pytest.raises(app_module.AppManagerError, match="not found"),
    ):
        app_module._get_executable("nonexistent-binary-xyz")


def test_run_raises_on_nonzero_exit() -> None:
    with (
        patch.object(
            app_module.subprocess,
            "run",
            return_value=app_module.subprocess.CompletedProcess(
                ["false"], 1, "", "command failed"
            ),
        ),
        pytest.raises(app_module.AppManagerError, match="Command failed"),
    ):
        app_module._run(["false"])


def test_main_add_command_with_install(tmp_path: Path) -> None:
    apps_file = tmp_path / "apps.toml"
    argv = [
        "app",
        "--apps-file",
        str(apps_file),
        "add",
        "httpie",
        "uv",
        "-g",
        "cli",
        "-d",
        "desc",
    ]
    with (
        patch.object(sys, "argv", argv),
        patch.object(app_module, "install_app") as install,
        patch.object(app_module, "uninstall_app") as uninstall,
    ):
        app_module.main()
        install.assert_called_once()
        uninstall.assert_not_called()


def test_main_add_with_source_change_calls_uninstall(tmp_path: Path) -> None:
    apps_file = tmp_path / "apps.toml"
    apps_file.write_text('[cli]\nhttpie = "formula"\n')
    argv = [
        "app",
        "--apps-file",
        str(apps_file),
        "add",
        "httpie",
        "uv",
        "-g",
        "cli",
        "-d",
        "desc",
    ]
    with (
        patch.object(sys, "argv", argv),
        patch.object(app_module, "install_app") as install,
        patch.object(app_module, "uninstall_app") as uninstall,
    ):
        app_module.main()
        install.assert_called_once()
        uninstall.assert_called_once()
        call_kwargs = uninstall.call_args[1]
        assert call_kwargs["source"] == "formula"
        assert call_kwargs["app"] == "httpie"


def test_main_add_command(tmp_path: Path) -> None:
    apps_file = tmp_path / "apps.toml"
    argv = [
        "app",
        "--apps-file",
        str(apps_file),
        "add",
        "httpie",
        "uv",
        "-g",
        "cli",
        "-d",
        "desc",
        "--no-install",
    ]
    with (
        patch.object(sys, "argv", argv),
        patch.object(app_module, "save_apps") as save,
    ):
        app_module.main()
        save.assert_called_once()


def test_main_remove_command_with_install() -> None:
    doc = tomlkit.parse('[cli]\nhttpie = "uv"\n')
    with (
        patch.object(sys, "argv", ["app", "remove", "httpie"]),
        patch.object(app_module, "load_apps", return_value=doc),
        patch.object(app_module, "save_apps") as save,
        patch.object(app_module, "uninstall_app") as uninstall,
    ):
        app_module.main()
        save.assert_called_once()
        uninstall.assert_called_once_with(doc, source="uv", app="httpie")


def test_main_remove_command() -> None:
    doc = tomlkit.parse('[cli]\nhttpie = "uv"\n')
    with (
        patch.object(sys, "argv", ["app", "remove", "httpie", "--no-install"]),
        patch.object(app_module, "load_apps", return_value=doc),
        patch.object(app_module, "save_apps") as save,
    ):
        app_module.main()
        save.assert_called_once()


def test_main_info_command(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch.object(
            app_module,
            "parse_args",
            return_value=argparse.Namespace(
                command="info",
                app="gh",
                source="formula",
                apps_file=Path("apps.toml"),
            ),
        ),
        patch.object(
            app_module,
            "load_apps",
            return_value=tomlkit.parse('[dev]\ngh = "formula"\n'),
        ),
        patch.object(
            app_module,
            "fetch_app_info",
            return_value=app_module.AppInfo(
                name="gh",
                source="formula",
                description="GitHub CLI",
                website="https://cli.github.com",
                version="2.0",
                installed=True,
            ),
        ),
    ):
        app_module.main()
    output = capsys.readouterr().out
    assert "gh" in output
    assert "formula" in output


def test_main_sync_command() -> None:
    with (
        patch.object(
            app_module,
            "parse_args",
            return_value=argparse.Namespace(
                command="sync",
                apps_file=Path("apps.toml"),
                install_cask=True,
                install_formula=True,
                install_uv=True,
                install_mas=True,
            ),
        ),
        patch.object(app_module, "load_apps", return_value=tomlkit.document()),
        patch.object(app_module, "sync_apps") as sync,
    ):
        app_module.main()
        sync.assert_called_once()


def test_main_list_command(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch.object(sys, "argv", ["app", "list"]),
        patch.object(
            app_module,
            "load_apps",
            return_value=tomlkit.parse('[x]\nfoo = "uv"\n'),
        ),
    ):
        app_module.main()
    output = capsys.readouterr().out
    assert "foo" in output or "No apps" in output


def test_main_unknown_command_raises() -> None:
    with (
        patch.object(
            app_module,
            "parse_args",
            return_value=argparse.Namespace(
                command="unknown",
                apps_file=Path("apps.toml"),
            ),
        ),
        patch.object(app_module, "load_apps", return_value=tomlkit.document()),
        pytest.raises(app_module.AppManagerError, match="Unknown command"),
    ):
        app_module.main()


def test_infer_description_from_fetch() -> None:
    with (
        patch.object(
            app_module,
            "fetch_app_info",
            return_value=app_module.AppInfo(
                name="gh",
                source="formula",
                description="GitHub CLI",
                website=None,
                version=None,
                installed=False,
            ),
        ),
    ):
        result = app_module.infer_description("formula", "gh", None, tomlkit.document())
    assert result == "GitHub CLI"


def test_infer_description_raises_when_unknown() -> None:
    with (
        patch.object(
            app_module,
            "fetch_app_info",
            return_value=app_module.AppInfo(
                name="gh",
                source="formula",
                description=None,
                website=None,
                version=None,
                installed=False,
            ),
        ),
        pytest.raises(
            app_module.AppManagerError,
            match="Could not determine description",
        ),
    ):
        app_module.infer_description("formula", "gh", None, tomlkit.document())


def test_list_installed_uv() -> None:
    with (
        patch.object(app_module, "_get_executable", return_value="uv"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(
                stdout="httpie  v1.0.0\n-rust-something\n",
                returncode=0,
            ),
        ),
    ):
        result = app_module._list_installed_uv()
    assert "httpie" in result


def test_list_installed_mas() -> None:
    with (
        patch.object(app_module, "_get_executable", return_value="mas"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(
                stdout="409203825 Numbers (1.0)\n",
                returncode=0,
            ),
        ),
    ):
        result = app_module._list_installed_mas()
    assert "409203825" in result
    assert result["409203825"] == "Numbers"


def test_print_missing_apps(capsys: pytest.CaptureFixture[str]) -> None:
    app_module._print_missing_apps("Header", ["item1", "item2"])
    output = capsys.readouterr().out
    assert "Header" in output
    assert "item1" in output
    assert "item2" in output


def test_sanitize_toml_inline_comment() -> None:
    assert app_module.sanitize_toml_inline_comment("a\nb\nc") == "a b c"


def test_iter_apps_by_source() -> None:
    doc = tomlkit.parse('[dev]\ngh = "formula"\n[x]\nfoo = "cask"\n')
    by_source = app_module._iter_apps_by_source(doc)
    assert "formula" in by_source
    assert "cask" in by_source
    assert ("dev", "gh") in by_source["formula"]
    assert ("x", "foo") in by_source["cask"]


def test_source_enabled() -> None:
    args = SimpleNamespace(install_cask=True, install_formula=False)
    assert app_module._source_enabled("cask", args)
    assert not app_module._source_enabled("formula", args)


def test_enabled_sources() -> None:
    args = SimpleNamespace(
        install_cask=True,
        install_formula=True,
        install_uv=False,
        install_mas=True,
    )
    sources = app_module._enabled_sources(args)
    assert "cask" in sources
    assert "formula" in sources
    assert "mas" in sources
    assert "uv" not in sources


def test_build_installed_state() -> None:
    args = SimpleNamespace(
        install_cask=True,
        install_formula=True,
        install_uv=True,
        install_mas=True,
    )
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout="", returncode=0),
        ),
        patch.object(app_module, "_list_installed_uv", return_value=[]),
        patch.object(app_module, "_list_installed_mas", return_value={}),
    ):
        state = app_module._build_installed_state(args)
    assert state.casks == set()
    assert state.formulas == set()
    assert state.uv == set()
    assert state.mas == {}


def test_install_declared_apps_skips_disabled_source() -> None:
    doc = tomlkit.parse('[cli]\nhttpie = "uv"\n[casks]\nchrome = "cask"\n')
    args = SimpleNamespace(
        install_cask=False,
        install_formula=True,
        install_uv=True,
        install_mas=True,
    )
    state = app_module.InstalledState(casks=set(), formulas=set(), uv=set(), mas={})
    with patch.object(app_module, "_install_from_source") as install_from:
        app_module._install_declared_apps(doc, args, state)
        install_from.assert_called_once_with(app="httpie", source="uv", state=state)


def test_install_declared_apps() -> None:
    doc = tomlkit.parse('[cli]\nhttpie = "uv"\n')
    args = SimpleNamespace(
        install_cask=True,
        install_formula=True,
        install_uv=True,
        install_mas=True,
    )
    state = app_module.InstalledState(casks=set(), formulas=set(), uv=set(), mas={})
    with (
        patch.object(app_module, "_install_from_source") as install_from,
    ):
        app_module._install_declared_apps(doc, args, state)
        install_from.assert_called_once_with(app="httpie", source="uv", state=state)


def test_get_macos_only_formulas_returns_macos_only_formulas() -> None:
    brew_json = json.dumps({
        "formulae": [
            {
                "name": "macos-only-tool",
                "full_name": "homebrew/core/macos-only-tool",
                "requirements": [{"name": "macos"}],
                "bottle": {
                    "stable": {
                        "files": {"arm64_monterey": {}, "x86_64_sonoma": {}},
                    },
                },
            },
        ],
    })
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout=brew_json, returncode=0, stderr=""),
        ),
    ):
        result = app_module._get_macos_only_formulas(["macos-only-tool"])
    assert "macos-only-tool" in result
    assert "homebrew/core/macos-only-tool" in result


def test_get_macos_only_formulas_excludes_linux_capable() -> None:
    brew_json = json.dumps({
        "formulae": [
            {
                "name": "linux-tool",
                "full_name": "homebrew/core/linux-tool",
                "requirements": [],
                "bottle": {
                    "stable": {
                        "files": {"x86_64_linux": {}, "arm64_linux": {}},
                    },
                },
            },
        ],
    })
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout=brew_json, returncode=0, stderr=""),
        ),
    ):
        result = app_module._get_macos_only_formulas(["linux-tool"])
    assert result == set()


def test_get_macos_only_formulas_empty_list() -> None:
    result = app_module._get_macos_only_formulas([])
    assert result == set()


def test_get_macos_only_formulas_invalid_json_returns_empty() -> None:
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout="invalid json", returncode=1, stderr=""),
        ),
    ):
        result = app_module._get_macos_only_formulas(["foo"])
    assert result == set()


def test_get_macos_only_formulas_batches_multiple_formulas() -> None:
    brew_json = json.dumps({
        "formulae": [
            {
                "name": "macos-tool",
                "full_name": "homebrew/core/macos-tool",
                "requirements": [{"name": "macos"}],
                "bottle": {"stable": {"files": {"arm64_monterey": {}}}},
            },
            {
                "name": "linux-tool",
                "full_name": "homebrew/core/linux-tool",
                "requirements": [],
                "bottle": {"stable": {"files": {"x86_64_linux": {}}}},
            },
            {
                "name": "another-macos-tool",
                "full_name": "homebrew/core/another-macos-tool",
                "requirements": [{"name": "macos"}],
                "bottle": {"stable": {"files": {"x86_64_monterey": {}}}},
            },
        ],
    })
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout=brew_json, returncode=0, stderr=""),
        ),
    ):
        result = app_module._get_macos_only_formulas([
            "macos-tool",
            "linux-tool",
            "another-macos-tool",
        ])
    assert "macos-tool" in result
    assert "homebrew/core/macos-tool" in result
    assert "another-macos-tool" in result
    assert "homebrew/core/another-macos-tool" in result
    assert "linux-tool" not in result
    assert "homebrew/core/linux-tool" not in result


def test_install_declared_apps_skips_macos_only_on_linux(
    capsys: pytest.CaptureFixture[str],
) -> None:
    doc = tomlkit.parse('[cli]\nmacos-tool = "formula"\nlinux-tool = "formula"\n')
    args = SimpleNamespace(
        install_cask=True,
        install_formula=True,
        install_uv=True,
        install_mas=True,
    )
    state = app_module.InstalledState(casks=set(), formulas=set(), uv=set(), mas={})
    brew_json = json.dumps({
        "formulae": [
            {
                "name": "macos-tool",
                "full_name": "homebrew/core/macos-tool",
                "requirements": [{"name": "macos"}],
                "bottle": {"stable": {"files": {"arm64_monterey": {}}}},
            },
            {
                "name": "linux-tool",
                "full_name": "homebrew/core/linux-tool",
                "requirements": [],
                "bottle": {"stable": {"files": {"x86_64_linux": {}}}},
            },
        ],
    })
    with (
        patch.object(app_module, "platform") as platform_mock,
        patch.object(platform_mock, "system", return_value="Linux"),
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout=brew_json, returncode=0, stderr=""),
        ),
        patch.object(app_module, "_install_from_source") as install_from,
    ):
        app_module._install_declared_apps(doc, args, state)
    output = capsys.readouterr().out
    assert "Skipping macos-tool (macOS only)" in output
    assert "linux-tool" not in output or "Skipping" not in output
    install_from.assert_called_once_with(app="linux-tool", source="formula", state=state)


def test_install_app_skips_macos_only_on_linux(capsys: pytest.CaptureFixture[str]) -> None:
    doc = tomlkit.parse("")
    brew_json = json.dumps({
        "formulae": [
            {
                "name": "macos-only-tool",
                "full_name": "homebrew/core/macos-only-tool",
                "requirements": [{"name": "macos"}],
                "bottle": {"stable": {"files": {"arm64_monterey": {}}}},
            },
        ],
    })
    with (
        patch.object(app_module, "platform") as platform_mock,
        patch.object(platform_mock, "system", return_value="Linux"),
        patch.object(
            app_module,
            "fetch_app_info",
            return_value=app_module.AppInfo(
                name="macos-only-tool",
                source="formula",
                description="A tool",
                website=None,
                version=None,
                installed=False,
            ),
        ),
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout=brew_json, returncode=0, stderr=""),
        ),
    ):
        app_module.install_app(doc, source="formula", app="macos-only-tool")
    output = capsys.readouterr().out
    assert "Skipping macos-only-tool (macOS only)" in output


def test_confirm_uninstall_auto_yes() -> None:
    assert app_module._confirm_uninstall(auto_yes=True)


def test_confirm_uninstall_prompts_no() -> None:
    with patch.object(builtins, "input", return_value="n"):
        result = app_module._confirm_uninstall(auto_yes=False)
    assert not result


def test_confirm_uninstall_prompts_yes() -> None:
    with patch.object(builtins, "input", return_value="y"):
        result = app_module._confirm_uninstall(auto_yes=False)
    assert result


def test_sync_homebrew_no_missing() -> None:
    apps_by_source = {
        "cask": [("g1", "chrome")],
        "formula": [("g1", "gh")],
        "uv": [],
        "mas": [],
    }
    args = SimpleNamespace(
        install_cask=True,
        install_formula=True,
        install_uv=True,
        install_mas=True,
        yes=False,
    )
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout="", returncode=0),
        ),
        patch.object(app_module, "_confirm_uninstall", return_value=True),
    ):
        app_module._sync_homebrew(apps_by_source, args)


def test_sync_uv_no_missing() -> None:
    apps_by_source = {"cask": [], "formula": [], "uv": [("cli", "httpie")], "mas": []}
    args = SimpleNamespace(install_uv=True, yes=False)
    with (
        patch.object(app_module, "_list_installed_uv", return_value=["httpie"]),
        patch.object(app_module, "_confirm_uninstall", return_value=True),
    ):
        app_module._sync_uv(apps_by_source, args)


def test_sync_uv_disabled_returns_early() -> None:
    args = SimpleNamespace(install_uv=False)
    with patch.object(app_module, "_list_installed_uv") as list_uv:
        app_module._sync_uv({"cask": [], "formula": [], "uv": [], "mas": []}, args)
        list_uv.assert_not_called()


def test_sync_mas_disabled_returns_early() -> None:
    args = SimpleNamespace(install_mas=False)
    with patch.object(app_module, "_list_installed_mas") as list_mas:
        app_module._sync_mas({"cask": [], "formula": [], "uv": [], "mas": []}, args)
        list_mas.assert_not_called()


def test_sync_mas_no_missing() -> None:
    apps_by_source = {
        "cask": [],
        "formula": [],
        "uv": [],
        "mas": [("apple", "409203825")],
    }
    args = SimpleNamespace(install_mas=True, yes=False)
    with (
        patch.object(
            app_module,
            "_list_installed_mas",
            return_value={"409203825": "Numbers"},
        ),
        patch.object(app_module, "_confirm_uninstall", return_value=True),
    ):
        app_module._sync_mas(apps_by_source, args)


def test_sync_homebrew_with_missing_uninstalls(capsys: pytest.CaptureFixture[str]) -> None:
    apps_by_source = {
        "cask": [],
        "formula": [],
        "uv": [],
        "mas": [],
    }
    args = SimpleNamespace(
        install_cask=True,
        install_formula=True,
        install_uv=True,
        install_mas=True,
        yes=True,
    )
    run_results = [
        SimpleNamespace(stdout="orphan-formula", returncode=0),
        SimpleNamespace(stdout="orphan-cask", returncode=0),
        SimpleNamespace(stdout="", returncode=0),
        SimpleNamespace(stdout="", returncode=0),
    ]
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            side_effect=run_results,
        ),
    ):
        app_module._sync_homebrew(apps_by_source, args)
    output = capsys.readouterr().out
    assert "Uninstalling" in output or "orphan" in output or "missing" in output.lower()


def test_sync_confirm_decline(capsys: pytest.CaptureFixture[str]) -> None:
    apps_by_source = {"cask": [], "formula": [], "uv": [], "mas": []}
    args = SimpleNamespace(
        install_cask=True,
        install_formula=True,
        install_uv=True,
        install_mas=True,
        yes=False,
    )
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(stdout="orphan", returncode=0),
        ),
        patch.object(app_module, "_confirm_uninstall", return_value=False),
    ):
        app_module._sync_homebrew(apps_by_source, args)
    assert "No apps were uninstalled" in capsys.readouterr().out


def test_sync_uv_decline_skips_uninstall(capsys: pytest.CaptureFixture[str]) -> None:
    apps_by_source = {"cask": [], "formula": [], "uv": [], "mas": []}
    args = SimpleNamespace(install_uv=True, yes=False)
    with (
        patch.object(app_module, "_list_installed_uv", return_value=["orphan"]),
        patch.object(app_module, "_confirm_uninstall", return_value=False),
    ):
        app_module._sync_uv(apps_by_source, args)
    assert "No apps were uninstalled" in capsys.readouterr().out


def test_sync_uv_with_missing_uninstalls() -> None:
    apps_by_source = {"cask": [], "formula": [], "uv": [], "mas": []}
    args = SimpleNamespace(install_uv=True, yes=True)
    with (
        patch.object(app_module, "_list_installed_uv", return_value=["orphan-tool"]),
        patch.object(app_module, "_get_executable", return_value="uv"),
        patch.object(app_module, "_run") as run,
    ):
        app_module._sync_uv(apps_by_source, args)
        run.assert_called()


def test_sync_mas_with_missing_uninstalls() -> None:
    apps_by_source = {"cask": [], "formula": [], "uv": [], "mas": []}
    args = SimpleNamespace(install_mas=True, yes=True)
    with (
        patch.object(
            app_module,
            "_list_installed_mas",
            return_value={"999": "Orphan App"},
        ),
        patch.object(app_module, "_get_executable", return_value="mas"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(returncode=0),
        ) as run,
    ):
        app_module._sync_mas(apps_by_source, args)
        run.assert_called()


def test_sync_mas_uninstall_failure(capsys: pytest.CaptureFixture[str]) -> None:
    apps_by_source = {"cask": [], "formula": [], "uv": [], "mas": []}
    args = SimpleNamespace(install_mas=True, yes=True)
    with (
        patch.object(
            app_module,
            "_list_installed_mas",
            return_value={"999": "Orphan App"},
        ),
        patch.object(app_module, "_get_executable", return_value="mas"),
        patch.object(
            app_module,
            "_run",
            return_value=SimpleNamespace(returncode=1),
        ),
    ):
        app_module._sync_mas(apps_by_source, args)
    output = capsys.readouterr().out
    assert "Failed" in output or "manual" in output.lower()


def test_update_and_cleanup() -> None:
    args = SimpleNamespace(
        install_cask=True,
        install_formula=True,
        install_uv=True,
        install_mas=True,
    )
    with (
        patch.object(app_module, "_get_executable", return_value="brew"),
        patch.object(app_module, "_run") as run,
    ):
        app_module._update_and_cleanup(args)
        assert run.call_count >= 3


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
