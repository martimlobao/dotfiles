#!/usr/bin/env bash
set -euo pipefail
trap "echo 'Script was interrupted by the user.'; exit 1" INT

###############################################################################
# SET UP PYTHON ENVIRONMENT                                                   #
###############################################################################

# Installs a package using Homebrew if it isn't installed yet.
# Usage: brew_install <package_name>
brew_install () {
	if ! brew list "$1" &> /dev/null; then
		echo -e "⬇️  \033[1;34mInstalling $1...\033[0m"
		brew install "$1"
	else
		echo -e "✅  \033[1;32m$1 is already installed.\033[0m"
	fi
}

brew_install rye
# This is needed for now since there is not official Homebrew installation for Rye yet, but it may not be needed in the future
if [ ! -f "$HOME/.rye/env" ]; then
	rye self install -y
fi

# Install pyenv and its plugins (might use rye instead of pyenv in the future, but for now install both)
brew_install pyenv
brew_install pyenv-virtualenv
brew_install pyenv-virtualenvwrapper

# Install latest Python
PYTHONVERSION=$(pyenv install --list | grep -Eo ' [0-9\.]+$' | tail -1 | sed -e 's/^[[:space:]]*//')
if ! pyenv versions | grep -q $PYTHONVERSION; then
	echo -e "🐍  \033[1;32mInstalling Python $PYTHONVERSION using Pyenv...\033[0m"
	pyenv install $PYTHONVERSION
	pyenv global $PYTHONVERSION
fi

brew_install pantsbuild/tap/pants
brew_install poetry
brew_install ipython

###############################################################################
# To create a virtual environment:
# $ pyenv virtualenv 3.12.2 myproject
#
# To set a local environment, use the following command in the project folder:
# $ pyenv local myproject
#
# To install packages, use pipenv instead of pip after setting and activating a local
# environment (pipenv respects the virtualenv it's launched in):
# $ pyenv virtualenv 3.12.2 myproject
# $ pyenv local myproject
# $ pipenv install requests
###############################################################################
