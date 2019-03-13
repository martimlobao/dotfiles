#!/usr/bin/env bash

# Ask for the administrator password upfront and keep alive until script has finished
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

###############################################################################
# INSTALL COMMAND-LINE TOOLS USING HOMEBREW                                   #
###############################################################################

# Update Homebrew and installed formulas.
brew update
brew upgrade

# Install Bash 4.
brew install bash
brew install bash-completion2

# Switch to using brew-installed bash as default shell.
BREW_PREFIX=$(brew --prefix)
if ! fgrep -q "${BREW_PREFIX}/bin/bash" /etc/shells; then
	echo "${BREW_PREFIX}/bin/bash" | sudo tee -a /etc/shells;
	chsh -s "${BREW_PREFIX}/bin/bash";
fi;

# Install git utilities.
brew install git
brew install git-lfs

# Install other languages.
brew install node

# Install download utilities.
brew install httpie
brew install wget
brew install youtube-dl

# Install fancy shell stuff.
brew install autojump
brew install mas
brew install nnn

# Install very important stuff.
brew install cowsay
brew install googler
brew install lolcat
brew install neofetch
brew install thefuck

# Install other useful binaries.
brew install exiftool
brew install imagemagick
brew install pandoc

# Remove outdated versions from the cellar.
brew cleanup
