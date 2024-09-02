#!/usr/bin/env bash
set -o errexit  # stop the script each time a command fails
set -o nounset  # stop if you attempt to use an undef variable

function bash_traceback() {
	local lasterr="$?"
	set +o xtrace
	local code="-1"
	local bash_command=${BASH_COMMAND}
	echo "Error in ${BASH_SOURCE[1]}:${BASH_LINENO[0]} ('$bash_command' exited with status $lasterr)" >&2
	if [ ${#FUNCNAME[@]} -gt 2 ]; then
		# Print out the stack trace described by $function_stack
		echo "Traceback of ${BASH_SOURCE[1]} (most recent call last):" >&2
		for ((i=0; i < ${#FUNCNAME[@]} - 1; i++)); do
		local funcname="${FUNCNAME[$i]}"
		[ "$i" -eq "0" ] && funcname=$bash_command
		echo -e "  ${BASH_SOURCE[$i+1]}:${BASH_LINENO[$i]}\\t$funcname" >&2
		done
	fi
	echo "Exiting with status ${code}" >&2
	exit "${code}"
}

# provide an error handler whenever a command exits nonzero
trap 'bash_traceback' ERR

# propagate ERR trap handler functions, expansions and subshells
set -o errtrace

###############################################################################
# SET UP PYTHON ENVIRONMENT                                                   #
###############################################################################

# Installs a package using Homebrew if it isn't installed yet.
# Usage: brew_install <package_name>
brew_install () {
	if ! brew list "$1" &> /dev/null; then
		echo -e "⬇️  \033[1;34mInstalling $1...\033[0m"
		if ! brew install "$1"; then
			echo -e "❌ \033[1;31mFailed to install $1. Please check manually.\033[0m"
		fi
	else
		echo -e "✅  \033[1;32m$1 is already installed.\033[0m"
	fi
}

brew_install uv

# Install pyenv and its plugins
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

# Default linter
brew_install ruff  # Consider using `uv tool install ruff` instead

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
