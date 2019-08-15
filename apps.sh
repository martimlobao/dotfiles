#!/usr/bin/env bash

###############################################################################
# INSTALL APPS AND SOFTWARE                                                   #
###############################################################################

# FONTS
brew cask install homebrew/cask-fonts/font-source-code-pro
brew cask install homebrew/cask-fonts/font-source-sans-pro
brew cask install homebrew/cask-fonts/font-humor-sans

# TOOLS
brew cask install aerial
brew cask install android-platform-tools
brew cask install java
brew cask install qlmarkdown
brew cask install qlstephen
brew cask install qlvideo
brew cask install quicklook-json
brew cask install webpquicklook
brew cask install xquartz

# APPLE
if [[ $WORKPC != true ]]; then
	mas install 409203825 # Numbers
	mas install 408981434 # iMovie
	mas install 409201541 # Pages
	mas install 409183694 # Keynote
fi

# DESIGN
brew cask install licecap
mas install 1081413713 # GIF Brewery 3
mas install 1351639930 # Gifski

# DEVELOPER
brew cask install atom
brew cask install jupyter-notebook-viewer
brew cask install mongodb-compass
brew cask install mysqlworkbench
brew cask install sublime-text
brew cask install tableau-public

# LEISURE
brew cask install spotify
brew cask install homebrew/cask-drivers/sonos
if [[ $WORKPC != true ]]; then
	brew cask install minecraft
fi

# PRODUCTIVITY
brew cask install dropbox
brew cask install slack # mas install 803453959
if [[ $WORKPC != true ]]; then
	brew cask install evernote # mas install 406056744
	mas install 410628904 # Wunderlist
fi

# SOCIAL
brew cask install houseparty # mas install 1381523962
brew cask install skype
if [[ $WORKPC != true ]]; then
	brew cask install telegram # mas install 747648890
	brew cask install whatsapp # mas install 1147396723
fi

# UTILITIES
brew cask install google-chrome
brew cask install the-unarchiver # mas install 425424353
brew cask install tunnelblick
if [[ $WORKPC != true ]]; then
	brew cask install istat-menus
	brew cask install transmission
	brew cask install vlc
	mas install 495945638 # Wake Up Time
fi
