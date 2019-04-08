#!/usr/bin/env bash

# Ask for the administrator password upfront and keep alive until script has finished
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

echo
echo "###############################################################################"
echo "# Install Homebrew                                                            #"
echo "###############################################################################"
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
# This command also installs Xcode Command Line Tools, which includes git
sudo installer -pkg /Library/Developer/CommandLineTools/Packages/macOS_SDK_headers_for_macOS_10.14.pkg -target /
# This may be needed on macOS Mojave to get pyenv to work

echo
echo "###############################################################################"
echo "# Install dotfiles                                                             #"
echo "###############################################################################"
./bootstrap.sh -f

echo
echo "###############################################################################"
echo "# Local settings and variables                                                #"
echo "###############################################################################"
sudo ./local.sh

echo
echo "###############################################################################"
echo "# macOS preferences                                                           #"
echo "###############################################################################"
sudo ./macos.sh

echo
echo "###############################################################################"
echo "# Install command-line tools using Homebrew                                   #"
echo "###############################################################################"
sudo ./brew.sh

echo
echo "###############################################################################"
echo "# Set up python environment                                                   #"
echo "###############################################################################"
./python.sh

echo
echo "###############################################################################"
echo "# Install apps and software                                                   #"
echo "###############################################################################"
./apps.sh
./dock.sh

echo
echo "###############################################################################"
echo "# Install private dotfiles                                                    #"
echo "###############################################################################"
git clone git@github.com:martimlobao/dotfiles-private.git
sudo ./dotfiles-private/run.sh 2> /dev/null

echo "Setup complete!"
