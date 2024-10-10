#!/usr/bin/env bash
set -euo pipefail
trap "echo 'Script was interrupted by the user.'; exit 1" INT

###############################################################################
# INSTALL APPS AND SOFTWARE                                                   #
###############################################################################

echo -e "📲  \033[1;36mInstalling apps and software...\033[0m"

# Installs a cask using Homebrew if it isn't installed yet.
# Usage: brew_install <cask_name>
brew_install () {
	if ! brew list --cask "$1" &> /dev/null; then
		echo -e "⬇️  \033[1;34mInstalling $1...\033[0m"
		if ! brew install --cask "$1"; then
			echo -e "❌ \033[1;31mFailed to install $1. Please check manually.\033[0m"
		fi
	else
		echo -e "✅  \033[1;32m$1 is already installed.\033[0m"
	fi
}

# Installs an app using MAS if it isn't installed yet.
# Note that mas can only install apps that you have previously downloaded from the App Store.
# Usage: mas_install <app_id>
mas_install () {
	if mas list | grep -q "$1 "; then
		APP_NAME=$(mas list | grep "$1 " | sed -E 's/.*[0-9]+[[:space:]]+(.*)[[:space:]]+\(.*/\1/' | sed -E 's/[[:space:]]*$//')
		echo -e "✅  \033[1;32m$APP_NAME is already installed from the App Store.\033[0m"
	else
		APP_NAME=$(mas info "$1" | head -n 1 | sed -E 's/(.*)[[:space:]]+[0-9\.]+ \[.*\]/\1/')
		echo -e "⬇️  \033[1;34mInstalling $APP_NAME from the App Store...\033[0m"
		mas install "$1"
	fi
}

# FONTS
brew_install font-fira-code
brew_install font-humor-sans
brew_install font-sauce-code-pro-nerd-font
brew_install font-source-code-pro
brew_install font-source-sans-3

# UTILITIES
brew_install chromedriver
brew_install qlmarkdown
brew_install qlstephen
brew_install qlvideo
brew_install quicklook-json
brew_install webpquicklook

# APPLE
mas_install 408981434  # iMovie
mas_install 409183694  # Keynote
mas_install 409201541  # Pages
mas_install 409203825  # Numbers

# DESIGN
brew_install licecap
mas_install 1351639930  # Gifski

# DEVELOPER
brew_install charles
brew_install docker
brew_install hyper
brew_install jupyter-notebook-viewer
brew_install visual-studio-code
brew_install warp

# LEISURE
brew_install minecraft
brew_install sonos
brew_install spotify
# mas_install 1048524688  # Delta - Game Emulator

# PRODUCTIVITY
brew_install chatgpt
brew_install notion
brew_install obsidian
brew_install sejda-pdf
brew_install slack  # mas install 803453959
brew_install todoist
brew_install zoom
mas_install 1274495053  # Microsoft To Do
mas_install 1423210932  # Flow - Focus & Pomodoro Timer

# SOCIAL
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
mas_install 937984704  # Amphetamine
