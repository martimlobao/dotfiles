#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# INSTALL APPS AND SOFTWARE                                                   #
###############################################################################

# Function for installing a cask using Homebrew if it doesn't exist
brew_install () {
	if ! brew list --cask $1 &> /dev/null; then
		echo -e "⬇️  \033[1;34mInstalling $1...\033[0m"
		brew install --cask $1
	else
		echo -e "☑️  \033[1;32m$1 is already installed.\033[0m"
	fi
}

# FONTS
brew_install homebrew/cask-fonts/font-fira-code
brew_install homebrew/cask-fonts/font-humor-sans
brew_install homebrew/cask-fonts/font-sauce-code-pro-nerd-font
brew_install homebrew/cask-fonts/font-source-code-pro
brew_install homebrew/cask-fonts/font-source-sans-3

# UTILITIES
brew_install qlmarkdown
brew_install qlstephen
brew_install qlvideo
brew_install quicklook-json
brew_install webpquicklook

# APPLE
mas install 408981434  # iMovie
mas install 409183694  # Keynote
mas install 409201541  # Pages
mas install 409203825  # Numbers

# DESIGN
brew_install licecap
mas install 1351639930  # Gifski

# DEVELOPER
brew_install docker
brew_install hyper
brew_install jupyter-notebook-viewer
brew_install visual-studio-code

# LEISURE
brew_install minecraft
brew_install sonos
brew_install spotify

# PRODUCTIVITY
brew_install evernote  # mas install 406056744
brew_install notion
brew_install obsidian
brew_install slack  # mas install 803453959
brew_install todoist
brew_install zoom

# SOCIAL
brew_install skype
brew_install telegram  # mas install 747648890
brew_install whatsapp  # mas install 1147396723

# TOOLS
brew_install 1password
brew_install arc
brew_install dropbox
brew_install expressvpn
brew_install google-chrome
brew_install google-drive
brew_install istat-menus
brew_install notunes
brew_install the-unarchiver  # mas install 425424353
brew_install transmission
brew_install tunnelblick
brew_install vlc
mas install 1274495053  # Microsoft To Do
mas install 1423210932  # Flow - Focus & Pomodoro Timer
mas install 937984704  # Amphetamine
