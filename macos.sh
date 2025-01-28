#!/usr/bin/env bash

# Root is $DOTPATH if it exists, otherwise the directory of this script
root=$(realpath "${DOTPATH:-$(dirname "$(realpath "$0")")}")

# Source the bash_traceback.sh file
source "${root}/bash_traceback.sh"

###############################################################################
# macOS preferences                                                           #
###############################################################################

echo -e "\033[1;34m💻 Setting macOS preferences...\033[0m"

# Enable TouchID for sudo
# https://jc0b.computer/posts/enabling-touchid-for-sudo-macos-sonoma/
if [[ ! -f /etc/pam.d/sudo_local ]]; then
	echo -e "🔑 \033[1;35mEnabling TouchID for sudo...\033[0m"
	sudo sh -c 'echo "auth       sufficient     pam_tid.so" >> /etc/pam.d/sudo_local'
	sudo chmod 444 /etc/pam.d/sudo_local
else
	echo -e "✅ \033[1;32mTouchID for sudo is already enabled.\033[0m"
fi
