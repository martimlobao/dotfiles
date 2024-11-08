set -e

# Homebrew
eval "$(brew --prefix)/bin/brew shellenv)"

eval "$(pyenv init -)"

# Add uv to PATH
export PATH="$HOME/.local/bin:$PATH"
