# Homebrew
eval "$(/opt/homebrew/bin/brew shellenv)"

# Add pyenv to PATH
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"

# Add rye to PATH
source "$HOME/.rye/env"
