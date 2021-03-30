#!/usr/bin/env bash

###############################################################################
# INSTALL APPS AND SOFTWARE                                                   #
###############################################################################

# FONTS
brew install --cask homebrew/cask-fonts/font-fira-code
brew install --cask homebrew/cask-fonts/font-humor-sans
brew install --cask homebrew/cask-fonts/font-source-code-pro
brew install --cask homebrew/cask-fonts/font-source-sans-pro

# TOOLS
brew install --cask aerial
brew install --cask android-platform-tools
brew install --cask java
brew install --cask qlmarkdown
brew install --cask qlstephen
brew install --cask qlvideo
brew install --cask quicklook-json
brew install --cask webpquicklook
brew install --cask xquartz

# APPLE
if [[ $WORKPC != true ]]; then
	mas install 409203825 # Numbers
	mas install 408981434 # iMovie
	mas install 409201541 # Pages
	mas install 409183694 # Keynote
fi

# DESIGN
brew install --cask licecap
mas install 1081413713 # GIF Brewery 3
mas install 1351639930 # Gifski

# DEVELOPER
brew install --cask docker
brew install --cask hyper
brew install --cask jupyter-notebook-viewer
brew install --cask mongodb-compass
brew install --cask mysqlworkbench
brew install --cask sublime-text
brew install --cask tableau-public
brew install --cask visual-studio-code

# LEISURE
brew install --cask sonos
brew install --cask spotify
if [[ $WORKPC != true ]]; then
	brew install --cask minecraft
	brew tap popcorn-official/popcorn-desktop https://github.com/popcorn-official/popcorn-desktop.git
	brew install --cask popcorn-time
fi

# PRODUCTIVITY
brew install --cask dropbox
brew install --cask slack # mas install 803453959
brew install --cask zoomus
if [[ $WORKPC != true ]]; then
	brew install --cask evernote # mas install 406056744
	mas install 410628904 # Wunderlist
fi

# SOCIAL
brew install --cask houseparty # mas install 1381523962
brew install --cask skype
if [[ $WORKPC != true ]]; then
	brew install --cask telegram # mas install 747648890
	brew install --cask whatsapp # mas install 1147396723
fi

# UTILITIES
brew install --cask expressvpn
brew install --cask google-chrome
brew install --cask the-unarchiver # mas install 425424353
brew install --cask tunnelblick
if [[ $WORKPC != true ]]; then
	brew install --cask istat-menus
	brew install --cask transmission
	brew install --cask vlc
	mas install 495945638 # Wake Up Time
fi
