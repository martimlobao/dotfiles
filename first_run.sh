#!/usr/bin/env bash

# Ask for the administrator password upfront and keep alive until script has finished
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

###############################################################################
# Install Homebrew                                                            #
###############################################################################
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
# This command also installs Xcode Command Line Tools, which includes git
sudo installer -pkg /Library/Developer/CommandLineTools/Packages/macOS_SDK_headers_for_macOS_10.14.pkg -target /
# This may be needed on macOS Mojave to get pyenv to work

###############################################################################
# Local settings and environment variables                                    #
###############################################################################
./local.sh

###############################################################################
# macOS preferences                                                           #
###############################################################################
./macos.sh

###############################################################################
# Install command-line tools using Homebrew                                   #
###############################################################################
./brew.sh

###############################################################################
# Set up python environment                                                   #
###############################################################################
./python.sh

###############################################################################
# Install apps and software                                                   #
###############################################################################
./apps.sh
./dock.sh

###############################################################################
# App preferences                                                             #
###############################################################################
apm install sync-settings
GIST_ID=eeee555
# GITHUB_TOKEN=aaaaaaa GIST_ID=aaaaa atom
GITHUB_TOKEN=$GITHUBTOKEN GIST_ID=$ATOMGISTID atom
# keep package tokens

###############################################################################
# Sync dotfiles                                                               #
###############################################################################
./bootstrap.sh
