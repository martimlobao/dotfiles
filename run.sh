#!/usr/bin/env bash

# Source the bash_traceback.sh file
source "$(dirname "$0")/bash_traceback.sh"

###############################################################################
# Install Homebrew                                                            #
###############################################################################
echo -e "\033[1;34m🍺 Installing Homebrew...\033[0m"
if ! command -v brew &> /dev/null; then
	/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
	echo -e "🍻 \033[1;32mHomebrew installed.\033[0m"
else
	echo -e "🍻 \033[1;32mHomebrew is already installed.\033[0m"
fi

###############################################################################
# Install dotfiles                                                            #
###############################################################################
sleep 1
echo
./dotsync.sh "${1:-}"

###############################################################################
# Local settings and variables                                                #
###############################################################################
sleep 1
echo
./local.sh "${1:-}"

###############################################################################
# macOS preferences                                                           #
###############################################################################
# sleep 1
# echo
# sudo ./macos.sh

###############################################################################
# Install apps and software                                                   #
###############################################################################
sleep 1
echo
./install.sh "${1:-}"
sleep 1
echo
./dock.sh

echo
echo -e "\033[1;32m🎉 Setup complete!\033[0m"
