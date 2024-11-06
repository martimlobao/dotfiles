#!/usr/bin/env bash

# Root is $DOTPATH if it exists, otherwise the directory of this script
root=$(realpath "${DOTPATH:-$(dirname "$(realpath "$0")")}")

# Source the bash_traceback.sh file
source "$root/bash_traceback.sh"

###############################################################################
# Install Homebrew                                                            #
###############################################################################
echo
echo -e "\033[1;33m🍺 Installing Homebrew...\033[0m"
if ! command -v brew &>/dev/null; then
	/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
	echo -e "🍻 \033[1;32mHomebrew installed.\033[0m"
else
	echo -e "🍻 \033[1;32mHomebrew is already installed.\033[0m"
fi

###############################################################################
# Install dotfiles                                                            #
###############################################################################
echo
echo -e "\033[1;33m🚀 Running dotsync.sh...\033[0m"
sleep 1
./dotsync.sh "${1:-}"

###############################################################################
# Local settings and variables                                                #
###############################################################################
echo
echo -e "\033[1;33m🚀 Running local.sh...\033[0m"
sleep 1
./local.sh "${1:-}"

###############################################################################
# macOS preferences                                                           #
###############################################################################
# sleep 1
# echo -e "\033[1;33m🚀 Running macos.sh...\033[0m"
# sudo ./macos.sh

###############################################################################
# Install apps and software                                                   #
###############################################################################
echo
echo -e "\033[1;33m🚀 Running install.sh...\033[0m"
sleep 1
./install.sh "${1:-}"
echo
echo -e "\033[1;33m🚀 Running dock.sh...\033[0m"
sleep 1
./dock.sh

echo
echo -e "\033[1;32m🎉 Setup complete!\033[0m"
