#!/usr/bin/env bash
set -euo pipefail

# Ask for the administrator password upfront and keep alive until script has finished
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

###############################################################################
# INSTALL COMMAND-LINE TOOLS USING HOMEBREW                                   #
###############################################################################

# Function for installing a command using Homebrew if it doesn't exist
brew_install () {
	if ! brew list $1 &> /dev/null; then
		echo -e "⬇️  \033[1;34mInstalling $1...\033[0m"
		brew install $1
	else
		echo -e "☑️  \033[1;32m$1 is already installed.\033[0m"
	fi
}

# Update Homebrew and installed formulas
brew update
brew upgrade

# Install newer version of zsh and install plugins
brew_install zsh
brew_install zsh-autosuggestions
brew_install zsh-syntax-highlighting

# Update shell to Homebrew zsh if not already set
if [ "$0" != "$(brew --prefix)/bin/zsh" ]; then
	chsh -s $(brew --prefix)/bin/zsh
else
	echo "✔ \033[1;32mShell is already set to $(brew --prefix)/bin/zsh.\033[0m"
fi

sudo chsh -s $(brew --prefix)/bin/zsh

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
brew_install 1password-cli op  # op is the command name
brew_install ack
brew_install exiftool
brew_install gifski
brew_install gpg
brew_install imagemagick
brew_install jq
brew_install pandoc
brew_install pastel
brew_install thefuck

# Install developer tools
brew_install docker
brew_install apache-spark
brew_install postgresql
brew_install redis

# Remove outdated versions from the cellar
brew cleanup
