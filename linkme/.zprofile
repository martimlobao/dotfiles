if [[ ${GITHUB_ACTIONS} == "true" ]]; then
    # Exit on error for CI
    set -e
fi

# Homebrew
eval "$("$(brew --prefix)/bin/brew" shellenv)"

# Add uv to PATH
export PATH="$HOME/.local/bin:$PATH"
