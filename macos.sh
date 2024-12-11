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

confirm_set() {
	while true; do
		read -rp "$1" "$2"
		read -rp "Set to '${!2}'? (y/n) "
		if [[ ${REPLY} =~ ^[Yy]$ ]]; then
			break
		fi
	done
}

# Set computer name
if [[ ${1-} == "-y" ]] || [[ ${1-} == "--yes" ]]; then
	echo -e "⏩ \033[1;34mRunning in non-interactive mode, skipping setting computer name.\033[0m"
else
	read -rp $'❓ \e[1;31mDo you want to (re)set the name for this computer? (currently set to '"$(scutil --get ComputerName)"') (y/n)'"$(tput sgr0)"' ' COMPUTERNAME
	if [[ ${COMPUTERNAME} =~ ^[Yy]$ ]]; then
		confirm_set "💻  Set the name for this computer: " COMPUTERNAME
		sudo scutil --set ComputerName "${COMPUTERNAME}"
		sudo scutil --set HostName "${COMPUTERNAME}"
		sudo scutil --set LocalHostName "${COMPUTERNAME}"
		sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.smb.server NetBIOSName -string "${COMPUTERNAME}"
	fi
fi
