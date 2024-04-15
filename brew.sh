#!/usr/bin/env bash
set -euo pipefail
trap "echo 'Script was interrupted by the user.'; exit 1" INT

###############################################################################
# INSTALL COMMAND-LINE TOOLS USING HOMEBREW                                   #
###############################################################################

echo -e "🛠️  \033[1;36mInstalling command-line tools using Homebrew...\033[0m"

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

# Update Homebrew and installed formulas
brew update
brew upgrade

# Install oh-my-zsh if it isn't installed yet
if [ ! -d "$HOME/.oh-my-zsh" ]; then
	echo -e "⬇️  \033[1;34mInstalling oh-my-zsh...\033[0m"
	sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
else
	echo -e "✅  \033[1;32moh-my-zsh is already installed.\033[0m"
fi

# Install zsh plugins
brew_install zsh-autosuggestions
brew_install zsh-syntax-highlighting

# Update system git and nano
brew_install git
brew_install nano

# # Install other languages
brew_install go
brew_install node
brew_install rust

# # Install download utilities
brew_install httpie
brew_install mas
brew_install wget
brew_install youtube-dl

# Install fancy shell stuff
brew_install autojump
brew_install bat
brew_install nnn
brew_install tree

# Install very important stuff
brew_install cowsay
brew_install lolcat

# Install newer versions of system binaries using different names
brew_install gsed
brew_install grep  # ggrep is the command name

# Install other useful binaries
brew_install 1password-cli  # op is the command name
brew_install ack
brew_install exiftool
brew_install imagemagick
brew_install jq
brew_install pandoc
brew_install pastel
brew_install shellcheck
brew_install thefuck

# Install developer tools
brew_install docker
brew_install postgresql
brew_install redis

# Remove outdated versions from the cellar
brew cleanup
