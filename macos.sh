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
		read -rp "❓ Set to '${!2}'? (y/n) "
		if [[ ${REPLY} =~ ^[Yy]$ ]]; then
			break
		fi
	done
}

# Set computer name
set_computer_name() {
	local interactive=$1

	local uuid
	local serial
	local model
	uuid=$(system_profiler SPHardwareDataType | awk '/Hardware UUID/ {print $3}')
	serial=$(system_profiler SPHardwareDataType | awk '/Serial Number/ {print $4}')
	model=$(sysctl hw.model | sed 's/hw.model: //')

	echo -e "🔍 \033[1;35mLooking up computer name on 1Password for ${uuid}...\033[0m"
	local name
	name=$(op read "op://Private/Computers/${uuid}/name" 2>/dev/null || echo '')
	if [[ -z ${name} ]]; then
		echo -e "🤔 \033[1;33mNew computer, who dis? (UUID: ${uuid})\033[0m"
		if [[ ${interactive} != "true" ]]; then
			echo -e "💡 \033[1;33mRun in interactive mode to set a name for this computer\033[0m"
			return 0
		fi
		confirm_set "💻 Set the name for this computer: " name
		echo -e "💾 \033[1;35mSaving computer name to 1Password...\033[0m"
		op item edit --vault Private Computers "${uuid}.name[text]=${name}" &>/dev/null
		op item edit --vault Private Computers "${uuid}.serial number[text]=${serial}" &>/dev/null
		op item edit --vault Private Computers "${uuid}.model[text]=${model}" &>/dev/null
		echo -e "✅ \033[1;32mComputer name set and saved to 1Password\033[0m"
	fi

	echo -e "💾 \033[1;35mSetting computer name to '${name}'...\033[0m"
	sudo scutil --set ComputerName "${name}"
	sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.smb.server NetBIOSName -string "${name}"
	# Replace spaces with underscores for host names
	name=$(echo "${name}" | tr ' ' '_')
	sudo scutil --set LocalHostName "${name}"
	sudo scutil --set HostName "${name}"
	echo -e "✅ \033[1;32mComputer name set\033[0m"
}

# Set interactive mode based on command line args
INTERACTIVE="true"
if [[ ${1-} == "-y" ]] || [[ ${1-} == "--yes" ]]; then
	INTERACTIVE="false"
fi

set_computer_name "${INTERACTIVE}"
