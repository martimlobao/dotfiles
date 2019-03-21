#!/usr/bin/env bash

###############################################################################
# INSTALL APPS AND SOFTWARE                                                   #
###############################################################################

# FONTS
brew cask install homebrew/cask-fonts/font-source-code-pro
brew cask install homebrew/cask-fonts/font-source-sans-pro

# TOOLS
brew cask install aerial
brew cask install android-platform-tools
brew cask install java
brew cask install qlmarkdown
brew cask install qlstephen
brew cask install quicklook-json
brew cask install webpquicklook
brew cask install xquartz

# APPLE
echo "Installing Numbers..."
mas install 409203825
echo "Installing GarageBand..."
mas install 682658836
echo "Installing iMovie..."
mas install 408981434
echo "Installing Pages..."
mas install 409201541
echo "Installing Keynote..."
mas install 409183694

# DESIGN
echo "Installing LICEcap..."
brew cask install licecap
echo "Installing GIF Brewery 3..."
mas install 1081413713
# Adobe Acrobat DC
# Adobe Illustrator CC 2018
# Adobe InDesign CC 2018
# Adobe Lightroom Classic CC
# Adobe Photoshop CC 2018
# Vector Magic.app

# DEVELOPER
echo "Installing Atom..."
brew cask install atom
echo "Installing MongoDB Compass..."
brew cask install mongodb-compass
echo "Installing MySQLWorkbench..."
brew cask install mysqlworkbench
echo "Installing Sublime Text..."
brew cask install sublime-text
echo "Installing Tableau..."
brew cask install tableau-public
# Mathematica.app
# WolframScript.app

# LEISURE
echo "Installing Spotify..."
brew cask install spotify
echo "Installing Sonos..."
brew cask install homebrew/cask-drivers/sonos
echo "Installing Minecraft..."
brew cask install minecraft

# OFFICE
# Microsoft Excel.app
# Microsoft OneNote.app
# Microsoft PowerPoint.app
# Microsoft Word.app

# PRODUCTIVITY
echo "Installing Dropbox..."
brew cask install dropbox
echo "Installing Evernote..."
brew cask install evernote # mas install 406056744
echo "Installing Slack..."
brew cask install slack # mas install 803453959
echo "Installing Wunderlist..."
mas install 410628904

# SOCIAL
echo "Installing Houseparty..."
mas install 1381523962
echo "Installing Skype..."
brew cask install skype
echo "Installing Telegram..."
brew cask install telegram # mas install 747648890
echo "Installing WhatsApp..."
brew cask install whatsapp # mas install 1147396723

# UTILITIES
echo "Installing Google Chrome..."
brew cask install google-chrome
echo "Installing InsomniaX..."
brew cask install insomniax
echo "Installing iStat Menus..."
brew cask install istat-menus
echo "Installing The Unarchiver..."
brew cask install the-unarchiver # mas install 425424353
echo "Installing Transmission..."
brew cask install transmission
echo "Installing Tunnelblick..."
brew cask install tunnelblick
echo "Installing VLC..."
brew cask install vlc
echo "Installing Wake Up Time..."
mas install 495945638
# echo "Installing CleanMyMac X..."
# brew cask install cleanmymac
# Parallels Desktop
