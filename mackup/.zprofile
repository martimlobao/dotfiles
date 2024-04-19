# Homebrew
eval "$(/opt/homebrew/bin/brew shellenv)"

# Add pyenv to PATH
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
export PYENV_VIRTUALENVWRAPPER_PREFER_PYVENV="true"
eval "$(pyenv init --path)"
eval "$(pyenv virtualenv-init -)"

# Add rye to PATH
source "$HOME/.rye/env"
