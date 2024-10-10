#!/usr/bin/env bash

# Bash traceback (from https://gist.github.com/Asher256/4c68119705ffa11adb7446f297a7beae)
set -o errexit  # stop the script each time a command fails
set -o nounset  # stop if you attempt to use an undef variable

function bash_traceback() {
	local lasterr="$?"
	set +o xtrace
	local code="-1"
	local bash_command=${BASH_COMMAND}
	echo "Error in ${BASH_SOURCE[1]}:${BASH_LINENO[0]} ('$bash_command' exited with status $lasterr)" >&2
	if [ ${#FUNCNAME[@]} -gt 2 ]; then
		# Print out the stack trace described by $function_stack
		echo "Traceback of ${BASH_SOURCE[1]} (most recent call last):" >&2
		for ((i=0; i < ${#FUNCNAME[@]} - 1; i++)); do
		local funcname="${FUNCNAME[$i]}"
		[ "$i" -eq "0" ] && funcname=$bash_command
		echo -e "  ${BASH_SOURCE[$i+1]}:${BASH_LINENO[$i]}\\t$funcname" >&2
		done
	fi
	echo "Exiting with status ${code}" >&2
	exit "${code}"
}

# provide an error handler whenever a command exits nonzero
trap 'bash_traceback' ERR

# propagate ERR trap handler functions, expansions and subshells
set -o errtrace

# Ask for the administrator password upfront and keep alive until script has finished
echo -e "🦸  \033[1;34mRequesting admin permissions...\033[0m"
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

###############################################################################
# LOCAL SETTINGS AND VARIABLES                                                #
###############################################################################

confirm_set () {
	while true; do
		read -rp "$1" "$2"
		read -rp "Set to '${!2}'? (y/n) "
		if [[ $REPLY =~ ^[Yy]$ ]]; then
			break
		fi
	done
}

# Set computer name
read -rp $'❓  \e[1;31mDo you want to (re)set the name for this computer? (y/n) \e[0m ' SETNAME
if [[ $SETNAME =~ ^[Yy]$ ]]; then
	confirm_set "💻  Set the name for this computer: " COMPUTERNAME
	sudo scutil --set ComputerName "$COMPUTERNAME"
	sudo scutil --set HostName "$COMPUTERNAME"
	sudo scutil --set LocalHostName "$COMPUTERNAME"
	sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.smb.server NetBIOSName -string "$COMPUTERNAME"
fi

# Set up .gitconfig.private
echo -e "📝  \033[1;34mSetting up .gitconfig.private...\033[0m"
USERNAME=$(op user get --me | grep 'Name:' | sed 's/Name: *//')
	if [ -n "$USERNAME" ]; then
	    git config --file=$HOME/.gitconfig.private user.name "$USERNAME"
	else
	    echo "Error: User name is empty."
	    exit 1
	fi
git config --file=$HOME/.gitconfig.private user.email "$(op read "op://Private/Github/email")"
git config --file=$HOME/.gitconfig.private user.signingKey "$(op read "op://Private/Github SSH Commit Signing Key/public key")"
git config --file=$HOME/.gitconfig.private github.user "$(op read "op://Private/Github/username")"

# Copy all files from manual/ to ~/
read -rp $'❓  \e[1;31mDo you want to copy and overwrite all files from manual/ to $HOME? (y/n) \e[0m ' COPYMANUAL
if [[ $COPYMANUAL =~ ^[Yy]$ ]]; then
	cp -r manual/ ~/
fi

# iStat Menus
if [[ -z $(defaults read com.bjango.istatmenus license6) ]]; then
	echo -e "📝  \033[1;34mRegistering iStat Menus...\033[0m"
	defaults write com.bjango.istatmenus _modelid -string $(sysctl hw.model | sed 's/hw.model: //')
	defaults write com.bjango.istatmenus installDateV6 -int $(date -v +14d +%s)

	ISTAT_EMAIL=$(op read "op://Private/iStat Menus 6/registered email")
	ISTAT_KEY=$(op read "op://Private/iStat Menus 6/license key")
	/usr/libexec/PlistBuddy -c "Add :license6 dict" ~/Library/Preferences/com.bjango.istatmenus.plist
	/usr/libexec/PlistBuddy -c "Add :license6:email string $ISTAT_EMAIL" ~/Library/Preferences/com.bjango.istatmenus.plist
	/usr/libexec/PlistBuddy -c "Add :license6:serial string $ISTAT_KEY" ~/Library/Preferences/com.bjango.istatmenus.plist

	echo -e "✅  \033[1;32miStat Menus registered successfully.\033[0m"
else
	echo -e "✅  \033[1;32miStat Menus is already registered.\033[0m"
fi

# Charles
if [[ -z $(xmllint --xpath "string(//configuration/registrationConfiguration/key)" ~/Library/Preferences/com.xk72.charles.config) ]]; then
	echo -e "📝  \033[1;34mRegistering Charles...\033[0m"

	CHARLES_NAME=$(op read "op://Private/Charles/registered name")
	CHARLES_KEY=$(op read "op://Private/Charles/license key")
	# use printf instead of echo to avoid issues with newline characters in bash (not a problem with zsh)
	printf 'cd /configuration/registrationConfiguration/name\nset %s\nsave\n' "$CHARLES_NAME" | xmllint --shell ~/Library/Preferences/com.xk72.charles.config 2>&1 >/dev/null
	printf 'cd /configuration/registrationConfiguration/key\nset %s\nsave\n' "$CHARLES_KEY" | xmllint --shell ~/Library/Preferences/com.xk72.charles.config 2>&1 >/dev/null

	echo -e "✅  \033[1;32mCharles registered successfully.\033[0m"
else
	echo -e "✅  \033[1;32mCharles is already registered.\033[0m"
fi
