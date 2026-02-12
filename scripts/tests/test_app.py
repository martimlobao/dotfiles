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
from unittest.mock import Mock, patch

import pytest
import tomlkit

SPEC = importlib.util.spec_from_file_location("app_module", Path("scripts/app.py"))
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("failed to load scripts/app.py")
app = importlib.util.module_from_spec(SPEC)
sys.modules["app_module"] = app
SPEC.loader.exec_module(app)
app_module: ModuleType = app


def make_result(
    *,
    stdout: str = "",
    returncode: int = 0,
    stderr: str = "",
) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, returncode=returncode, stderr=stderr)


def build_facade(
    tmp_path: Path,
    *,
    content: str = "",
    runner: object | None = None,
) -> tuple[object, Path, object]:
    apps_file = tmp_path / "apps.toml"
    if content:
        apps_file.write_text(content)
    console = app_module.Console()
    repo = app_module.AppsRepository(apps_file, console=console)
    runner = runner or Mock(spec=app_module.CommandRunner)
    facade = app_module.AppManagerFacade(repository=repo, runner=runner, console=console)
    return facade, apps_file, runner


def test_source_registry_has_expected_sources() -> None:
    assert set(app_module.SourceRegistry.source_names()) == {"cask", "formula", "uv", "mas"}


def test_source_registry_create_unknown_raises() -> None:
    with pytest.raises(app_module.AppManagerError, match="Unknown source"):
        app_module.SourceRegistry.create(
            "unknown",
            runner=Mock(spec=app_module.CommandRunner),
            console=app_module.Console(),
        )


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


def test_command_runner_get_executable_raises() -> None:
    runner = app_module.CommandRunner()
    with (
        patch.object(app_module.shutil, "which", return_value=None),
        pytest.raises(app_module.AppManagerError, match="not found"),
    ):
        runner.get_executable("missing")


def test_command_runner_run_raises_on_nonzero() -> None:
    runner = app_module.CommandRunner()
    with (
        patch.object(
            app_module.subprocess,
            "run",
            return_value=app_module.subprocess.CompletedProcess(["false"], 1, "", "failed"),
        ),
        pytest.raises(app_module.AppManagerError, match="Command failed"),
    ):
        runner.run(["false"])


def test_console_paint_with_icon(capsys: pytest.CaptureFixture[str]) -> None:
    console = app_module.Console()
    console.paint("hello", app_module.Ansi.GREEN, icon="✅")
    output = capsys.readouterr().out
    assert "hello" in output
    assert "✅" in output


def test_console_prompt_yes_no_auto() -> None:
    console = app_module.Console()
    assert console.prompt_yes_no("Proceed? ", auto_yes=True)


def test_console_prompt_yes_no_input() -> None:
    console = app_module.Console()
    with patch.object(builtins, "input", return_value="n"):
        assert not console.prompt_yes_no("Proceed? ", auto_yes=False)


def test_console_render_records_empty(capsys: pytest.CaptureFixture[str]) -> None:
    console = app_module.Console()
    console.render_records([])
    assert "No apps found." in capsys.readouterr().out


def test_repository_resolve_group_name_case_insensitive(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[CLI-Tools]\nhttpie = "uv"\n')
    document = facade.repository.load()
    assert facade.repository.resolve_group_name(document, "cli-tools") == "CLI-Tools"


def test_repository_resolve_group_name_empty_raises(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    with pytest.raises(app_module.AppManagerError, match="cannot be empty"):
        facade.repository.resolve_group_name(tomlkit.document(), "  ")


def test_repository_validate_duplicates_raises(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    doc = tomlkit.parse('[one]\nfoo = "uv"\n[two]\nFoo = "cask"\n')
    with pytest.raises(app_module.AppManagerError, match="Duplicate apps found"):
        facade.repository.validate_no_duplicates(doc)


def test_repository_load_creates_missing_file(tmp_path: Path) -> None:
    facade, apps_file, _ = build_facade(tmp_path)
    document = facade.repository.load()
    assert apps_file.exists()
    assert list(document.items()) == []


def test_repository_find_app_case_insensitive(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nHTTPie = "uv"\n')
    document = facade.repository.load()
    record = facade.repository.find_app(document, "httpie")
    assert record is not None
    assert record.key == "HTTPie"
    assert record.source == "uv"


def test_repository_sanitize_comment() -> None:
    assert app_module.AppsRepository.sanitize_toml_inline_comment("a\nb\nc") == "a b c"


def test_repository_remove_app_from_group_removes_section(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nfoo = "formula"\n')
    document = facade.repository.load()
    removed = facade.repository.remove_app_from_group(document, group="dev", app_key="foo")
    assert removed
    assert "dev" not in document


def test_repository_remove_app_from_group_keeps_section(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nfoo = "formula"\nbar = "cask"\n')
    document = facade.repository.load()
    removed = facade.repository.remove_app_from_group(document, group="dev", app_key="foo")
    assert removed
    assert "dev" in document
    assert "bar" in document["dev"]


def test_repository_add_or_update_new(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nfoo = "formula"\n')
    document = facade.repository.load()
    outcome = facade.repository.add_or_update(
        document,
        app="bar",
        source="cask",
        group="tools",
        description="new desc",
    )
    assert not outcome.existed
    assert outcome.previous_source is None
    assert document["tools"]["bar"] == "cask"


def test_repository_add_or_update_existing_move_and_source_change(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nfoo = "formula"\n')
    document = facade.repository.load()
    outcome = facade.repository.add_or_update(
        document,
        app="foo",
        source="cask",
        group="tools",
        description="new",
    )
    assert not outcome.existed
    assert outcome.moved_from == "dev"
    assert outcome.previous_source == "formula"
    assert "dev" not in document
    assert document["tools"]["foo"] == "cask"


def test_repository_add_or_update_raises_when_remove_fails(tmp_path: Path) -> None:
    facade, _, _ = build_facade(
        tmp_path, content='[dev]\nfoo = "formula"\n[tools]\nbar = "cask"\n'
    )
    document = facade.repository.load()
    with (
        patch.object(facade.repository, "remove_app_from_group", return_value=False),
        pytest.raises(app_module.AppManagerError, match="could not be removed"),
    ):
        facade.repository.add_or_update(
            document,
            app="foo",
            source="cask",
            group="tools",
            description="desc",
        )


def test_repository_remove_existing(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nfoo = "formula"\n')
    document = facade.repository.load()
    outcome = facade.repository.remove(document, "foo")
    assert outcome.removed
    assert outcome.source == "formula"


def test_repository_remove_missing(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nfoo = "formula"\n')
    document = facade.repository.load()
    outcome = facade.repository.remove(document, "bar")
    assert not outcome.removed


def test_repository_list_grouped_records(tmp_path: Path) -> None:
    facade, _, _ = build_facade(
        tmp_path,
        content='[cli]\nhttpie = "uv"  # HTTP client\n[dev]\ngh = "formula"  # GitHub CLI\n',
    )
    grouped = facade.repository.list_grouped_records(facade.repository.load())
    assert grouped
    assert grouped[0][0] == "cli"
    assert grouped[0][1][0].description == "HTTP client"


def test_brew_cask_fetch_info() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "brew"
    runner.run.return_value = make_result(
        stdout=json.dumps({
            "casks": [{"desc": "Browser", "homepage": "https://example.com", "installed": "1.0"}]
        }),
    )
    service = app_module.BrewCaskSourceService(runner=runner, console=app_module.Console())
    info = service.fetch_info("chrome", repo=Mock(), document=tomlkit.document())
    assert info.source == "cask"
    assert info.description == "Browser"
    assert info.installed
    assert info.version == "1.0"


def test_brew_formula_fetch_info_uninstalled_with_stable_version() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "brew"
    runner.run.return_value = make_result(
        stdout=json.dumps({
            "formulae": [
                {
                    "desc": "CLI",
                    "homepage": "https://example.com",
                    "versions": {"stable": "2.0"},
                }
            ],
        })
    )
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    info = service.fetch_info("gh", repo=Mock(), document=tomlkit.document())
    assert info.source == "formula"
    assert not info.installed
    assert info.version == "2.0"


def test_brew_fetch_info_raises_when_empty() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "brew"
    runner.run.return_value = make_result(stdout=json.dumps({"casks": []}))
    service = app_module.BrewCaskSourceService(runner=runner, console=app_module.Console())
    with pytest.raises(app_module.AppManagerError, match="No casks"):
        service.fetch_info("missing", repo=Mock(), document=tomlkit.document())


def test_brew_cask_find_unmanaged() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "brew"
    runner.run.return_value = make_result(stdout="managed\norphan\n")
    service = app_module.BrewCaskSourceService(runner=runner, console=app_module.Console())
    missing = service.find_unmanaged({"managed"})
    assert [item.identifier for item in missing] == ["orphan"]


def test_brew_formula_find_unmanaged() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "brew"
    runner.run.return_value = make_result(stdout="managed\norphan\n")
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    missing = service.find_unmanaged({"managed"})
    assert [item.identifier for item in missing] == ["orphan"]


def test_brew_cask_uninstall_unmanaged_uses_zap() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "brew"
    runner.run.return_value = make_result()
    service = app_module.BrewCaskSourceService(runner=runner, console=app_module.Console())
    service.uninstall_unmanaged("orphan")
    runner.run.assert_called_once_with(
        ["brew", "uninstall", "--cask", "--zap", "orphan"],
        capture_output=False,
    )


def test_formula_get_macos_only_formulas() -> None:
    brew_json = json.dumps({
        "formulae": [
            {
                "name": "macos-tool",
                "full_name": "homebrew/core/macos-tool",
                "requirements": [{"name": "macos"}],
                "bottle": {"stable": {"files": {"arm64_monterey": {}}}},
            },
        ]
    })
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "brew"
    runner.run.return_value = make_result(stdout=brew_json)
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    result = service.get_macos_only_formulas(["macos-tool"])
    assert "macos-tool" in result
    assert "homebrew/core/macos-tool" in result


def test_formula_get_macos_only_formulas_invalid_json_returns_empty() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "brew"
    runner.run.return_value = make_result(stdout="invalid", returncode=1)
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    assert service.get_macos_only_formulas(["x"]) == set()


def test_formula_pre_install_check_skips_on_linux() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    with patch.object(app_module.platform, "system", return_value="Linux"):
        service._linux_macos_only_cache = {"macos-only-tool"}
        result = service.pre_install_check("macos-only-tool")
    assert result is not None
    assert result.skipped
    assert "Skipping" in result.message


def test_formula_pre_install_check_none_on_darwin() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    with patch.object(app_module.platform, "system", return_value="Darwin"):
        assert service.pre_install_check("anything") is None


def test_uv_list_installed_parses_output() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "uv"
    runner.run.return_value = make_result(stdout="httpie  v1.0\n-rust-something\n")
    service = app_module.UvSourceService(runner=runner, console=app_module.Console())
    installed = service.list_installed()
    assert "httpie" in installed
    assert "-rust-something" not in installed


def test_uv_fetch_info_with_description(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[cli]\nhttpie = "uv"  # HTTP client\n')
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "uv"
    runner.run.return_value = make_result(stdout="httpie  v1.0.0\n")
    service = app_module.UvSourceService(runner=runner, console=app_module.Console())
    info = service.fetch_info("httpie", repo=facade.repository, document=facade.repository.load())
    assert info.description == "HTTP client"
    assert info.installed


def test_uv_find_unmanaged() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "uv"
    runner.run.return_value = make_result(stdout="managed  v1\norphan  v2\n")
    service = app_module.UvSourceService(runner=runner, console=app_module.Console())
    missing = service.find_unmanaged({"managed"})
    assert [item.identifier for item in missing] == ["orphan"]


def test_mas_list_installed() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "mas"
    runner.run.return_value = make_result(stdout="409203825 Numbers (1.0)\n")
    service = app_module.MasSourceService(runner=runner, console=app_module.Console())
    installed = service.list_installed()
    assert installed["409203825"] == "Numbers"


def test_mas_fetch_info() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "mas"
    runner.run.side_effect = [
        make_result(stdout="Numbers  1.0 [foo]\nFrom: https://example.com\n"),
        make_result(stdout="409203825 Numbers (1.0)\n"),
    ]
    service = app_module.MasSourceService(runner=runner, console=app_module.Console())
    info = service.fetch_info("409203825", repo=Mock(), document=tomlkit.document())
    assert info.source == "mas"
    assert info.description == "Numbers"
    assert info.installed


def test_mas_fetch_info_parse_error_raises() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "mas"
    runner.run.return_value = make_result(stdout="\n")
    service = app_module.MasSourceService(runner=runner, console=app_module.Console())
    with pytest.raises(app_module.AppManagerError, match="Could not parse"):
        service.fetch_info("1", repo=Mock(), document=tomlkit.document())


def test_mas_uninstall_failure_returns_failed_result() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "mas"
    runner.run.return_value = make_result(returncode=1)
    service = app_module.MasSourceService(runner=runner, console=app_module.Console())
    result = service.uninstall("1")
    assert not result.success


def test_base_strategy_ensure_installed_skips_when_installed() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.UvSourceService(runner=runner, console=app_module.Console())
    with patch.object(service, "is_installed", return_value=True):
        result = service.ensure_installed("foo")
    assert result.skipped


def test_base_strategy_ensure_uninstalled_skips_when_not_installed() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.UvSourceService(runner=runner, console=app_module.Console())
    with patch.object(service, "is_installed", return_value=False):
        result = service.ensure_uninstalled("foo")
    assert result.skipped


def test_base_strategy_ensure_uninstalled_success() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.UvSourceService(runner=runner, console=app_module.Console())
    with (
        patch.object(service, "is_installed", return_value=True),
        patch.object(service, "uninstall", return_value=app_module.OperationResult.ok("")),
    ):
        result = service.ensure_uninstalled("foo")
    assert result.success
    assert not result.skipped


def test_facade_infer_description_requires_uv(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    with pytest.raises(app_module.AppManagerError, match="Description is required"):
        facade._infer_description(
            source="uv",
            app="httpie",
            description=None,
            document=tomlkit.document(),
        )


def test_facade_infer_description_from_source(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    service = Mock()
    service.fetch_info.return_value = app_module.AppInfo(
        name="gh",
        source="formula",
        description="GitHub CLI",
        website=None,
        version=None,
        installed=False,
    )
    with patch.object(facade, "get_service", return_value=service):
        description = facade._infer_description(
            source="formula",
            app="gh",
            description=None,
            document=tomlkit.document(),
        )
    assert description == "GitHub CLI"


def test_facade_pick_group_interactively_number(tmp_path: Path) -> None:
    facade, _, _ = build_facade(
        tmp_path, content='[dev]\nfoo = "formula"\n[tools]\nbar = "cask"\n'
    )
    document = facade.repository.load()
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=True),
        patch.object(builtins, "input", side_effect=["1"]),
    ):
        assert facade.pick_group_interactively(document) == "dev"


def test_facade_pick_group_interactively_new_group(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nfoo = "formula"\n')
    document = facade.repository.load()
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=True),
        patch.object(builtins, "input", side_effect=["0", "newgroup"]),
    ):
        assert facade.pick_group_interactively(document) == "newgroup"


def test_facade_pick_group_interactively_not_tty_raises(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=False),
        pytest.raises(app_module.AppManagerError, match="not interactive"),
    ):
        facade.pick_group_interactively(tomlkit.document())


def test_facade_add_app_no_install(tmp_path: Path) -> None:
    facade, apps_file, _ = build_facade(tmp_path, content='[dev]\nfoo = "formula"\n')
    facade.add_app(
        app="bar",
        source="cask",
        group="tools",
        description="desc",
        no_install=True,
    )
    text = apps_file.read_text()
    assert "[tools]" in text
    assert 'bar = "cask"' in text


def test_facade_add_app_source_change_calls_uninstall_and_install(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[cli]\nhttpie = "formula"\n')
    previous_source_service = Mock()
    previous_source_service.ensure_uninstalled.return_value = app_module.OperationResult.ok("ok")
    new_source_service = Mock()
    new_source_service.ensure_installed.return_value = app_module.OperationResult.ok("ok")

    def service_for(source: str) -> object:
        return {"formula": previous_source_service, "uv": new_source_service}[source]

    with patch.object(facade, "get_service", side_effect=service_for):
        facade.add_app(
            app="httpie",
            source="uv",
            group="cli",
            description="desc",
            no_install=False,
        )

    previous_source_service.ensure_uninstalled.assert_called_once_with("httpie")
    new_source_service.ensure_installed.assert_called_once_with("httpie")


def test_facade_add_app_rolls_back_when_install_fails(tmp_path: Path) -> None:
    initial_text = '[cli]\nfoo = "formula"\n'
    facade, apps_file, _ = build_facade(tmp_path, content=initial_text)
    service = Mock()
    service.ensure_installed.side_effect = app_module.AppManagerError("install failed")

    with (
        patch.object(facade, "get_service", return_value=service),
        pytest.raises(app_module.AppManagerError, match="install failed"),
    ):
        facade.add_app(
            app="bar",
            source="uv",
            group="cli",
            description="desc",
            no_install=False,
        )

    assert apps_file.read_text() == initial_text


def test_facade_remove_app_not_found(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    facade, _, _ = build_facade(tmp_path, content='[cli]\nhttpie = "uv"\n')
    facade.remove_app(app="missing", no_install=False)
    assert "not found" in capsys.readouterr().out


def test_facade_remove_app_with_uninstall(tmp_path: Path) -> None:
    facade, apps_file, _ = build_facade(tmp_path, content='[cli]\nhttpie = "uv"\n')
    service = Mock()
    service.ensure_uninstalled.return_value = app_module.OperationResult.ok("ok")
    with patch.object(facade, "get_service", return_value=service):
        facade.remove_app(app="httpie", no_install=False)
    assert "httpie" not in apps_file.read_text()
    service.ensure_uninstalled.assert_called_once_with("httpie")


def test_facade_list_apps_calls_console(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[x]\nfoo = "uv"\n')
    with patch.object(facade.console, "render_records") as render:
        facade.list_apps()
        render.assert_called_once()


def test_facade_print_info_calls_service(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    service = Mock()
    service.fetch_info.return_value = app_module.AppInfo(
        name="gh",
        source="formula",
        description="GitHub CLI",
        website=None,
        version="1",
        installed=True,
    )
    with (
        patch.object(facade, "get_service", return_value=service),
        patch.object(facade.console, "print_info") as printer,
    ):
        facade.print_info(app="gh", source="formula")
        printer.assert_called_once()


def test_facade_prime_source_caches_formula(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    runner = Mock(spec=app_module.CommandRunner)
    formula_service = app_module.BrewFormulaSourceService(runner=runner, console=facade.console)
    grouped = [("dev", [app_module.AppRecord("dev", "gh", "formula", "")])]
    options = app_module.SyncOptions(yes=False, enabled_sources={"formula"})
    with (
        patch.object(facade, "get_service", return_value=formula_service),
        patch.object(formula_service, "prime_linux_skip_cache") as prime,
    ):
        facade._prime_source_caches(grouped, options)
        prime.assert_called_once_with(["gh"])


def test_facade_install_declared_skips_disabled_source(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    uv_service = Mock()
    uv_service.ensure_installed.return_value = app_module.OperationResult.ok("ok")
    cask_service = Mock()
    grouped = [
        (
            "cli",
            [
                app_module.AppRecord("cli", "httpie", "uv", ""),
                app_module.AppRecord("cli", "chrome", "cask", ""),
            ],
        )
    ]
    options = app_module.SyncOptions(yes=False, enabled_sources={"uv"})

    def service_for(source: str) -> object:
        return {"uv": uv_service, "cask": cask_service}[source]

    with patch.object(facade, "get_service", side_effect=service_for):
        facade._install_declared(grouped, options)

    uv_service.ensure_installed.assert_called_once_with("httpie")
    cask_service.ensure_installed.assert_not_called()


def test_facade_sync_unmanaged_no_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    facade, _, _ = build_facade(tmp_path)
    uv_service = Mock()
    uv_service.maintenance_key = "uv"
    uv_service.managed_aliases.return_value = {"httpie"}
    uv_service.find_unmanaged.return_value = []
    grouped = [("cli", [app_module.AppRecord("cli", "httpie", "uv", "")])]
    options = app_module.SyncOptions(yes=False, enabled_sources={"uv"})

    with patch.object(facade, "get_service", return_value=uv_service):
        facade._sync_unmanaged(grouped, options)

    output = capsys.readouterr().out
    assert "All uv-installed apps are present" in output


def test_facade_sync_unmanaged_decline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    facade, _, _ = build_facade(tmp_path)
    uv_service = Mock()
    uv_service.maintenance_key = "uv"
    uv_service.managed_aliases.return_value = {"httpie"}
    uv_service.find_unmanaged.return_value = [
        app_module.UnmanagedApp(source="uv", identifier="orphan", display="orphan")
    ]
    grouped = [("cli", [app_module.AppRecord("cli", "httpie", "uv", "")])]
    options = app_module.SyncOptions(yes=False, enabled_sources={"uv"})

    with (
        patch.object(facade, "get_service", return_value=uv_service),
        patch.object(facade.console, "prompt_yes_no", return_value=False),
    ):
        facade._sync_unmanaged(grouped, options)

    output = capsys.readouterr().out
    assert "No apps were uninstalled" in output
    uv_service.uninstall_unmanaged.assert_not_called()


def test_facade_sync_unmanaged_uninstalls(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    uv_service = Mock()
    uv_service.maintenance_key = "uv"
    uv_service.managed_aliases.return_value = {"httpie"}
    uv_service.find_unmanaged.return_value = [
        app_module.UnmanagedApp(source="uv", identifier="orphan", display="orphan")
    ]
    uv_service.uninstall_unmanaged.return_value = app_module.OperationResult.ok("")
    grouped = [("cli", [app_module.AppRecord("cli", "httpie", "uv", "")])]
    options = app_module.SyncOptions(yes=True, enabled_sources={"uv"})

    with patch.object(facade, "get_service", return_value=uv_service):
        facade._sync_unmanaged(grouped, options)

    uv_service.uninstall_unmanaged.assert_called_once_with("orphan")


def test_facade_sync_unmanaged_handles_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    facade, _, _ = build_facade(tmp_path)
    mas_service = Mock()
    mas_service.maintenance_key = "mas"
    mas_service.managed_aliases.return_value = {"123"}
    mas_service.find_unmanaged.return_value = [
        app_module.UnmanagedApp(source="mas", identifier="999", display="Orphan (999)")
    ]
    mas_service.uninstall_unmanaged.return_value = app_module.OperationResult.failed("failed")

    grouped = [("apple", [app_module.AppRecord("apple", "123", "mas", "")])]
    options = app_module.SyncOptions(yes=True, enabled_sources={"mas"})

    with patch.object(facade, "get_service", return_value=mas_service):
        facade._sync_unmanaged(grouped, options)

    assert "failed" in capsys.readouterr().out


def test_facade_upgrade_sources_deduplicates_provider(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    cask = Mock()
    cask.maintenance_key = "brew"
    formula = Mock()
    formula.maintenance_key = "brew"

    def service_for(source: str) -> object:
        return {"cask": cask, "formula": formula}[source]

    with patch.object(facade, "get_service", side_effect=service_for):
        facade._upgrade_sources(
            app_module.SyncOptions(yes=True, enabled_sources={"cask", "formula"})
        )

    total_calls = cask.upgrade_all.call_count + formula.upgrade_all.call_count
    assert total_calls == 1


def test_facade_sync_apps_orchestrates(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nfoo = "uv"\n')
    with (
        patch.object(facade, "_prime_source_caches") as prime,
        patch.object(facade, "_install_declared") as install_declared,
        patch.object(facade, "_sync_unmanaged") as sync_unmanaged,
        patch.object(facade, "_upgrade_sources") as upgrade,
    ):
        facade.sync_apps(app_module.SyncOptions(yes=True, enabled_sources={"uv"}))
    prime.assert_called_once()
    install_declared.assert_called_once()
    sync_unmanaged.assert_called_once()
    upgrade.assert_called_once()


def test_provider_sync_messages() -> None:
    header, ok = app_module.AppManagerFacade._provider_sync_messages("brew")
    assert "Homebrew" in header
    assert "present" in ok


def test_provider_sync_messages_default() -> None:
    header, ok = app_module.AppManagerFacade._provider_sync_messages("custom")
    assert "custom" in header
    assert "custom" in ok


def test_dispatcher_unknown_command_raises(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    dispatcher = app_module.CommandDispatcher(facade=facade)
    with pytest.raises(app_module.AppManagerError, match="Unknown command"):
        dispatcher.dispatch(argparse.Namespace(command="nope"))


def test_add_command_executes_facade(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    with patch.object(facade, "add_app") as add:
        cmd = app_module.AddAppCommand(facade=facade)
        cmd.execute(
            argparse.Namespace(
                app="foo",
                source="uv",
                group="cli",
                description="desc",
                no_install=True,
            )
        )
        add.assert_called_once()


def test_remove_command_executes_facade(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    with patch.object(facade, "remove_app") as remove:
        cmd = app_module.RemoveAppCommand(facade=facade)
        cmd.execute(argparse.Namespace(app="foo", no_install=True))
        remove.assert_called_once_with(app="foo", no_install=True)


def test_list_command_executes_facade(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    with patch.object(facade, "list_apps") as list_apps:
        cmd = app_module.ListAppsCommand(facade=facade)
        cmd.execute(argparse.Namespace())
        list_apps.assert_called_once()


def test_info_command_executes_facade(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    with patch.object(facade, "print_info") as info:
        cmd = app_module.InfoAppCommand(facade=facade)
        cmd.execute(argparse.Namespace(app="gh", source="formula"))
        info.assert_called_once_with(app="gh", source="formula")


def test_sync_command_builds_options_and_executes_facade(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    args = argparse.Namespace(
        command="sync",
        yes=True,
        install_cask=False,
        install_formula=True,
        install_uv=True,
        install_mas=False,
    )
    with patch.object(facade, "sync_apps") as sync:
        cmd = app_module.SyncAppsCommand(facade=facade)
        cmd.execute(args)
        sync.assert_called_once()
        options = sync.call_args[0][0]
        assert options.enabled_sources == {"formula", "uv"}


def test_main_list_command(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch.object(sys, "argv", ["app", "--apps-file", "apps.toml", "list"]),
        patch.object(
            app_module.AppsRepository, "load", return_value=tomlkit.parse('[x]\nfoo = "uv"\n')
        ),
    ):
        app_module.main()
    output = capsys.readouterr().out
    assert "foo" in output or "No apps" in output


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
        patch.object(app_module.SourceRegistry, "create") as create,
    ):
        service = Mock()
        service.fetch_info.return_value = app_module.AppInfo(
            name="gh",
            source="formula",
            description="GitHub CLI",
            website="https://cli.github.com",
            version="2.0",
            installed=True,
        )
        create.return_value = service
        app_module.main()
    output = capsys.readouterr().out
    assert "gh" in output
    assert "formula" in output


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
        pytest.raises(app_module.AppManagerError, match="Unknown command"),
    ):
        app_module.main()


def test_add_app_outcome_source_changed_property() -> None:
    outcome = app_module.AddAppOutcome(
        app_key="foo",
        group="dev",
        description="desc",
        existed=True,
        moved_from=None,
        previous_source="formula",
    )
    assert outcome.source_changed


def test_command_runner_get_executable_success() -> None:
    runner = app_module.CommandRunner()
    with patch.object(app_module.shutil, "which", return_value="/bin/echo"):
        assert runner.get_executable("echo") == "/bin/echo"


def test_command_runner_run_success() -> None:
    runner = app_module.CommandRunner()
    completed = app_module.subprocess.CompletedProcess(["echo"], 0, "ok", "")
    with patch.object(app_module.subprocess, "run", return_value=completed):
        result = runner.run(["echo"])
    assert result.stdout == "ok"


def test_console_paint_styles_when_tty() -> None:
    console = app_module.Console()
    with patch.object(app_module.sys.stdout, "isatty", return_value=True):
        rendered = console.paint("hello", app_module.Ansi.GREEN, print_it=False)
    assert "\x1b[" in rendered


def test_console_render_records_with_data(capsys: pytest.CaptureFixture[str]) -> None:
    console = app_module.Console()
    grouped = [
        (
            "cli",
            [
                app_module.AppRecord("cli", "httpie", "uv", "http client"),
                app_module.AppRecord("cli", "gh", "formula", "github cli"),
            ],
        )
    ]
    console.render_records(grouped)
    output = capsys.readouterr().out
    assert "httpie" in output
    assert "Source" in output


def test_console_emit_operation_branches(capsys: pytest.CaptureFixture[str]) -> None:
    console = app_module.Console()
    console.emit_operation(app_module.OperationResult.failed("bad"))
    console.emit_operation(app_module.OperationResult.skipped_result("skip"))
    output = capsys.readouterr().out
    assert "bad" in output
    assert "skip" in output


def test_console_helper_methods() -> None:
    assert app_module.Console._truncate("hello", 3) == "he…"
    assert app_module.Console._truncate("x", 1) == "x"
    assert not app_module.Console._truncate("x", 0)
    assert app_module.Console._visible_len("\x1b[31mred\x1b[0m") == 3
    console = app_module.Console()
    padded = console._ljust_ansi("\x1b[1mab\x1b[0m", 5)
    assert console._visible_len(padded) == 5


def test_repository_remove_app_from_group_when_group_not_table(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    document = tomlkit.document()
    document["dev"] = "not table"
    assert not facade.repository.remove_app_from_group(document, group="dev", app_key="foo")


def test_repository_remove_app_from_group_when_key_missing(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nfoo = "formula"\n')
    document = facade.repository.load()
    assert not facade.repository.remove_app_from_group(document, group="dev", app_key="bar")


def test_repository_add_or_update_raises_for_non_table_group(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    document = tomlkit.document()
    document["dev"] = "invalid"
    with pytest.raises(app_module.AppManagerError, match="is not a table"):
        facade.repository.add_or_update(
            document,
            app="foo",
            source="uv",
            group="dev",
            description="d",
        )


def test_repository_remove_returns_not_removed_when_internal_remove_fails(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nfoo = "formula"\n')
    document = facade.repository.load()
    with patch.object(facade.repository, "remove_app_from_group", return_value=False):
        outcome = facade.repository.remove(document, "foo")
    assert not outcome.removed


def test_repository_list_records_and_item_helpers(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content='[dev]\nfoo = "formula"  # x\n')
    document = facade.repository.load()
    records = facade.repository.list_records(document)
    assert len(records) == 1
    assert records[0].description == "x"

    class DummyItem:
        def __str__(self) -> str:
            return '"foo"'

    assert facade.repository.get_item_value(DummyItem()) == "foo"
    assert not facade.repository.get_item_comment(DummyItem())


def test_source_registry_duplicate_registration_raises() -> None:
    def _fetch_info(_self: object, *_args: object, **_kwargs: object) -> None:
        return None

    def _list_installed(_self: object) -> dict[str, str]:
        return {}

    def _install(_self: object, _app: str) -> None:
        return None

    def _uninstall(_self: object, _app: str) -> app_module.OperationResult:
        return app_module.OperationResult.ok("")

    def _upgrade_all(_self: object) -> None:
        return None

    def _find_unmanaged(_self: object, _managed: set[str]) -> list[app_module.UnmanagedApp]:
        return []

    with pytest.raises(app_module.AppManagerError, match="Duplicate source registration"):
        type(
            "AnotherUv",
            (app_module.BaseSourceService,),
            {
                "source_name": "uv",
                "install_flag": "install_uv",
                "sync_toggle_help": "x",
                "fetch_info": _fetch_info,
                "list_installed": _list_installed,
                "install": _install,
                "uninstall": _uninstall,
                "upgrade_all": _upgrade_all,
                "find_unmanaged": _find_unmanaged,
            },
        )


def test_base_source_properties_and_helpers() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    uv = app_module.UvSourceService(runner=runner, console=app_module.Console())
    assert uv.maintenance_key == "uv"

    mas = app_module.MasSourceService(runner=runner, console=app_module.Console())
    assert mas.managed_aliases("x") == {"x"}
    assert mas.pre_install_check("x") is None


def test_base_source_is_installed_uses_aliases() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.BrewCaskSourceService(runner=runner, console=app_module.Console())
    with patch.object(service, "list_installed", return_value={"httpie": "httpie"}):
        assert service.is_installed("homebrew/core/httpie")


def test_base_source_is_installed_caches_listed_state() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.BrewCaskSourceService(runner=runner, console=app_module.Console())
    with patch.object(service, "list_installed", return_value={"httpie": "httpie"}) as listed:
        assert service.is_installed("httpie")
        assert not service.is_installed("gh")
    listed.assert_called_once()


def test_base_source_cache_updates_after_install_and_uninstall() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.UvSourceService(runner=runner, console=app_module.Console())

    with (
        patch.object(service, "list_installed", return_value={}) as listed,
        patch.object(service, "install") as install,
        patch.object(
            service,
            "uninstall",
            return_value=app_module.OperationResult.ok(""),
        ) as uninstall,
    ):
        first = service.ensure_installed("httpie")
        second = service.ensure_installed("httpie")
        third = service.ensure_uninstalled("httpie")
        fourth = service.ensure_uninstalled("httpie")

    assert first.success
    assert not first.skipped
    assert second.skipped
    assert third.success
    assert not third.skipped
    assert fourth.skipped
    listed.assert_called_once()
    install.assert_called_once_with("httpie")
    uninstall.assert_called_once_with("httpie")


def test_base_source_ensure_installed_preflight_skip() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    with (
        patch.object(service, "is_installed", return_value=False),
        patch.object(
            service,
            "pre_install_check",
            return_value=app_module.OperationResult.skipped_result("Skipping foo (macOS only)"),
        ),
    ):
        result = service.ensure_installed("foo")
    assert result.skipped


def test_base_source_ensure_uninstalled_returns_failure() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.MasSourceService(runner=runner, console=app_module.Console())
    with (
        patch.object(service, "is_installed", return_value=True),
        patch.object(service, "uninstall", return_value=app_module.OperationResult.failed("no")),
    ):
        result = service.ensure_uninstalled("x")
    assert not result.success


def test_brew_source_methods_install_uninstall_upgrade_and_aliases() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "brew"
    runner.run.return_value = make_result()
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    assert service.managed_aliases("homebrew/core/gh") == {"homebrew/core/gh", "gh"}
    service.install("gh")
    service.uninstall("gh")
    service.upgrade_all()
    assert runner.run.call_count >= 5


def test_brew_extract_install_state_with_list() -> None:
    installed, version = app_module.BrewSourceService._extract_install_state({
        "installed": [{"version": "1.2.3"}]
    })
    assert installed
    assert version == "1.2.3"


def test_formula_prime_cache_darwin_noop() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    with (
        patch.object(app_module.platform, "system", return_value="Darwin"),
        patch.object(service, "get_macos_only_formulas") as get_macos_only,
    ):
        service.prime_linux_skip_cache(["gh"])
        get_macos_only.assert_not_called()


def test_formula_pre_install_check_without_cache_calls_lookup() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    with (
        patch.object(app_module.platform, "system", return_value="Linux"),
        patch.object(service, "get_macos_only_formulas", return_value=set()) as get_macos_only,
    ):
        result = service.pre_install_check("gh")
    assert result is None
    get_macos_only.assert_called_once_with(["gh"])


def test_formula_get_macos_only_formulas_empty_returns_empty() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    assert service.get_macos_only_formulas([]) == set()


def test_formula_get_macos_only_formulas_non_list_returns_empty() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "brew"
    runner.run.return_value = make_result(stdout=json.dumps({"formulae": {}}))
    service = app_module.BrewFormulaSourceService(runner=runner, console=app_module.Console())
    assert service.get_macos_only_formulas(["x"]) == set()


def test_formula_entry_is_macos_only_edge_cases() -> None:
    assert app_module.BrewFormulaSourceService._formula_entry_is_macos_only({}) == set()
    assert (
        app_module.BrewFormulaSourceService._formula_entry_is_macos_only({
            "requirements": [{"name": "macos"}],
            "bottle": {"stable": {"files": []}},
        })
        == set()
    )
    assert (
        app_module.BrewFormulaSourceService._formula_entry_is_macos_only({
            "requirements": [{"name": "macos"}],
            "bottle": {"stable": {"files": {"x86_64_linux": {}}}},
        })
        == set()
    )


def test_uv_fetch_info_ignores_short_lines() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "uv"
    runner.run.return_value = make_result(stdout="badline\n")
    service = app_module.UvSourceService(runner=runner, console=app_module.Console())
    info = service.fetch_info("httpie", repo=Mock(), document=tomlkit.document())
    assert not info.installed


def test_uv_install_uninstall_upgrade() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "uv"
    runner.run.return_value = make_result()
    service = app_module.UvSourceService(runner=runner, console=app_module.Console())
    service.install("httpie")
    service.uninstall("httpie")
    service.upgrade_all()
    assert runner.run.call_count == 3


def test_mas_list_installed_skips_invalid_lines() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "mas"
    runner.run.return_value = make_result(stdout="invalid\n409203825 Numbers (1.0)\n")
    service = app_module.MasSourceService(runner=runner, console=app_module.Console())
    installed = service.list_installed()
    assert "409203825" in installed


def test_mas_install_upgrade_and_successful_uninstall() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "mas"
    runner.run.return_value = make_result(returncode=0)
    service = app_module.MasSourceService(runner=runner, console=app_module.Console())
    service.install("123")
    result = service.uninstall("123")
    service.upgrade_all()
    assert result.success
    assert runner.run.call_count == 3


def test_mas_find_unmanaged() -> None:
    runner = Mock(spec=app_module.CommandRunner)
    runner.get_executable.return_value = "mas"
    runner.run.return_value = make_result(stdout="1 One (1.0)\n2 Two (1.0)\n")
    service = app_module.MasSourceService(runner=runner, console=app_module.Console())
    missing = service.find_unmanaged({"1"})
    assert [item.identifier for item in missing] == ["2"]


def test_facade_get_service_caches_instances(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, runner=Mock(spec=app_module.CommandRunner))
    with patch.object(app_module.SourceRegistry, "create") as create:
        create.return_value = Mock()
        first = facade.get_service("uv")
        second = facade.get_service("uv")
    assert first is second
    create.assert_called_once()


def test_facade_remove_app_no_install_returns_early(tmp_path: Path) -> None:
    facade, apps_file, _ = build_facade(tmp_path, content='[cli]\nhttpie = "uv"\n')
    with patch.object(facade, "get_service") as get_service:
        facade.remove_app(app="httpie", no_install=True)
        get_service.assert_not_called()
    assert "httpie" not in apps_file.read_text()


def test_facade_resolve_or_pick_group_without_group(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    with patch.object(facade, "pick_group_interactively", return_value="tools") as pick:
        result = facade._resolve_or_pick_group(tomlkit.document(), None)
    assert result == "tools"
    pick.assert_called_once()


def test_facade_pick_group_interactively_handles_empty_new_group_name(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=True),
        patch.object(builtins, "input", side_effect=["", "first"]),
    ):
        result = facade.pick_group_interactively(tomlkit.document())
    assert result == "first"


def test_facade_pick_group_interactively_retries_invalid_number(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content="[dev]\n[tools]\n")
    document = facade.repository.load()
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=True),
        patch.object(builtins, "input", side_effect=["99", "1"]),
    ):
        result = facade.pick_group_interactively(document)
    assert result == "dev"


def test_facade_pick_group_interactively_keyboard_interrupt_raises(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path, content="[dev]\n")
    document = facade.repository.load()
    with (
        patch.object(app_module.sys.stdin, "isatty", return_value=True),
        patch.object(builtins, "input", side_effect=KeyboardInterrupt),
        pytest.raises(app_module.AppManagerError, match="No group selected"),
    ):
        facade.pick_group_interactively(document)


def test_facade_infer_description_raises_when_source_has_none(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    service = Mock()
    service.fetch_info.return_value = app_module.AppInfo(
        name="x",
        source="formula",
        description=None,
        website=None,
        version=None,
        installed=False,
    )
    with (
        patch.object(facade, "get_service", return_value=service),
        pytest.raises(app_module.AppManagerError, match="Could not determine description"),
    ):
        facade._infer_description(
            source="formula",
            app="x",
            description=None,
            document=tomlkit.document(),
        )


def test_facade_prime_source_caches_returns_when_formula_disabled(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    with patch.object(facade, "get_service") as get_service:
        facade._prime_source_caches([], app_module.SyncOptions(yes=False, enabled_sources={"uv"}))
        get_service.assert_not_called()


def test_facade_prime_source_caches_returns_when_service_not_formula_type(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    with patch.object(facade, "get_service", return_value=Mock()):
        facade._prime_source_caches(
            [], app_module.SyncOptions(yes=False, enabled_sources={"formula"})
        )


def test_facade_install_declared_skip_message_branch(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    service = Mock()
    service.ensure_installed.return_value = app_module.OperationResult.skipped_result(
        "Skipping macos-tool (macOS only)"
    )
    grouped = [("cli", [app_module.AppRecord("cli", "macos-tool", "formula", "")])]
    with patch.object(facade, "get_service", return_value=service):
        facade._install_declared(
            grouped, app_module.SyncOptions(yes=False, enabled_sources={"formula"})
        )
    service.ensure_installed.assert_called_once()


def test_facade_sync_unmanaged_ignores_records_from_other_sources(tmp_path: Path) -> None:
    facade, _, _ = build_facade(tmp_path)
    uv_service = Mock()
    uv_service.maintenance_key = "uv"
    uv_service.managed_aliases.return_value = {"httpie"}
    uv_service.find_unmanaged.return_value = []
    grouped = [
        (
            "mixed",
            [
                app_module.AppRecord("mixed", "httpie", "uv", ""),
                app_module.AppRecord("mixed", "gh", "formula", ""),
            ],
        )
    ]
    with patch.object(facade, "get_service", return_value=uv_service):
        facade._sync_unmanaged(grouped, app_module.SyncOptions(yes=False, enabled_sources={"uv"}))


def test_parse_args_raises_when_no_sources_registered() -> None:
    with (
        patch.object(app_module.SourceRegistry, "source_names", return_value=[]),
        pytest.raises(app_module.AppManagerError, match="No sources are registered"),
    ):
        app_module.parse_args()
