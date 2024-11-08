if [[ ${CI} == "true" ]]; then
    # Exit on error for CI
    set -e
fi

# Homebrew
eval "/home/linuxbrew/.linuxbrew/bin/brew shellenv"
# eval "$("$(brew --prefix)/bin/brew" shellenv)"
# eval "$(/opt/homebrew/bin/brew shellenv)"

# Add uv to PATH
export PATH="$HOME/.local/bin:$PATH"
