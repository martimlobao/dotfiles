#!/usr/bin/env bash

# Source the bash_traceback.sh file
source "$(dirname "$0")/bash_traceback.sh"

###############################################################################
# Install Homebrew                                                            #
###############################################################################
echo -e "\033[1;34m🍺 Installing Homebrew...\033[0m"
sleep 1
if ! command -v brew &> /dev/null; then
	/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
	echo -e "🍻 \033[1;32mHomebrew installed.\033[0m"
else
	echo -e "🍻 \033[1;32mHomebrew is already installed.\033[0m"
fi

###############################################################################
# Install dotfiles                                                             #
###############################################################################
echo -e "\033[1;34m🔗 Installing dotfiles...\033[0m"
sleep 1
./dotsync.sh

###############################################################################
# Local settings and variables                                                #
###############################################################################
echo -e "\033[1;34m🔑 Setting local settings and variables...\033[0m"
sleep 1
./local.sh

###############################################################################
# macOS preferences                                                           #
###############################################################################
# echo -e "\033[1;34m💻 Setting macOS preferences...\033[0m"
# sleep 1
# sudo ./macos.sh

###############################################################################
# Install apps and software                                                   #
###############################################################################
echo -e "\033[1;34m📦 Installing apps and software...\033[0m"
sleep 1
./apps.sh
./dock.sh

echo -e "\033[1;32m🎉 Setup complete!\033[0m"
