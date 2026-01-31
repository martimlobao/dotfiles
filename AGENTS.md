# CLAUDE.md

This file provides guidance to AI agents like [Claude Code](https://claude.ai/code) when working
with code in this repository.

## Repository Overview

Personal macOS dotfiles with comprehensive setup automation. All scripts are idempotent and
designed primarily for macOS. Uses 1Password for secure credential management.

## Directory Structure

- **`linkme/`** - Files symlinked to home directory (shell config, `.zshrc`, `.aliases`,
  `.functions`, `.exports`, app configs)
- **`copyme/`** - Files copied to home directory (Library preferences that don't work as symlinks)
- **`injectme/`** - Templates for local user-specific config injection
- **`scripts/`** - Installation and configuration scripts
- **`apps.toml`** - Central catalog of all apps with installation metadata

## Commands

### Linting

```bash
make check              # Run all linters in parallel
make lint-shellcheck    # Shell script static analysis
make lint-shfmt         # Shell formatting
make lint-ruff          # Python linting
make lint-ruff-format   # Python formatting
make lint-ty            # Python type checking
make lint-rumdl         # Markdown linting
make lint-tombi         # TOML linting/formatting
make lint-yamllint      # YAML linting
make lint-trufflehog    # Secret detection
make lint-checkov       # Infrastructure security
```

### App Management

```bash
app add <name> <source> [--group <group>] [--description <text>]  # Add app to apps.toml and install
app remove <name>                                                 # Remove app from apps.toml and uninstall
app list                                                          # List all apps
# Sources: cask, formula, mas, uv
# Use --no-install to skip installation
```

### Running Scripts

```bash
./run.sh          # Full setup (Homebrew, dotfiles, apps, macOS settings)
syncapps          # Run install.sh to sync apps from apps.toml
bootstrap         # Run bootstrap.sh
aerials           # Download/manage macOS Aerial wallpapers
```

### Running Python Scripts Directly

```bash
uv run scripts/aerials.py   # Run with inline dependencies
uv run scripts/app.py       # CLI managed via shell function `app`
```

## Key Files

- **`bootstrap.sh`** - Entry point for fresh installs (downloads repo, runs `run.sh`)
- **`run.sh`** - Orchestrates full setup: Homebrew → dotsync → macos → install → dock → aerials →
  code → local
- **`apps.toml`** - TOML file listing all apps with source (cask/formula/mas/uv) and category
- **`linkme/.functions`** - Shell functions including `app`, `syncapps`, `aerials`, `bootstrap`
- **`linkme/.aliases`** - Shell aliases (`ls` → `eza`, navigation shortcuts, etc.)

## Commit/PR Title Format

PR titles are validated by `action-semantic-pull-request` using conventional commits format:

```
type(scope): description
```

- **Types:** `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `ci`, `perf`, `build`
- **Scope:** optional, in parentheses (e.g., `apps`, `deps`)
- **Description:** lowercase, no period at end
- **PR body:** keep it short (1-3 bullets), lowercase
- Examples: `feat(apps): add docker`, `fix: bad regex for csv diff`, `chore: update config`

## Code Patterns

- Shell scripts source `bash_traceback.sh` for better error reporting
- Python scripts use inline script dependencies (`# /// script`) for `uv run` compatibility
- Apps in `apps.toml` follow format: `name = "source"  # Description`
- Mac App Store apps use numeric IDs as keys
- Custom Homebrew taps use `tap/formula` format (e.g., `martimlobao/fonts/font-neacademia`)
