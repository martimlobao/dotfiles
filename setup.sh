#!/usr/bin/env bash

# Ask for the administrator password upfront and keep alive until script has finished
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

echo
echo "###############################################################################"
echo "# Install Homebrew                                                            #"
echo "###############################################################################"
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

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
./brew.sh

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
