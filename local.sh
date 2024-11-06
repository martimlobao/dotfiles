#!/usr/bin/env bash

# Root is $DOTPATH if it exists, otherwise the directory of this script
root=$(realpath "${DOTPATH:-$(dirname "$(realpath "$0")")}")

# Source the bash_traceback.sh file
source "$root/bash_traceback.sh"

###############################################################################
# LOCAL SETTINGS AND VARIABLES                                                #
###############################################################################

echo -e "\033[1;34m🔑 Setting local settings and variables...\033[0m"

# ensure signed in to 1Password
echo -e "🔐 \033[1;35mSigning in to 1Password...\033[0m"
op signin

# Set up .gitconfig.private
echo -e "📝 \033[1;35mSetting up .gitconfig.private...\033[0m"
USERNAME=$(op user get --me | grep 'Name:' | sed 's/Name: *//')
GITHUB_USER=$(op read "op://Private/GitHub/username")
EMAIL=$(op read "op://Private/GitHub/email")
SIGNING_KEY=$(op read "op://Private/GitHub SSH Commit Signing Key/public key")
if [ -n "$USERNAME" ] && [ -n "$EMAIL" ] && [ -n "$SIGNING_KEY" ] && [ -n "$GITHUB_USER" ]; then
	git config --file="$HOME"/.gitconfig.private user.name "$USERNAME"
	git config --file="$HOME"/.gitconfig.private user.email "$EMAIL"
	git config --file="$HOME"/.gitconfig.private user.signingKey "$SIGNING_KEY"
	git config --file="$HOME"/.gitconfig.private github.user "$GITHUB_USER"
else
	echo -e "❌ \033[1;31mError: One or more values for .gitconfig are not set. Exiting.\033[0m"
	exit 1
fi

# Copy all files from copyme/ to $HOME
if [[ ${1:-} != "--yes" ]] && [[ ${1:-} != "-y" ]]; then
	read -rp $'❓ \e[1;31mDo you want to copy and overwrite all files from copyme/ to $HOME? (y/n)\e[0m ' COPYME
else
	COPYME="y"
fi
if [[ $COPYME =~ ^[Yy]$ ]]; then
	rsync -av --exclude='.DS_Store' copyme/ "$HOME" |
		grep -v "building file list ... done" |
		awk '/^$/ { exit } !/\/$/ { printf "\033[1;32m📋 Copied %s\033[0m\n", $0; }'
fi

# iStat Menus
if [[ -z "$(defaults read com.bjango.istatmenus license6 2>/dev/null || echo '')" ]]; then
	echo -e "📝 \033[1;35mRegistering iStat Menus...\033[0m"
	ISTAT_EMAIL=$(op read "op://Private/iStat Menus 6/registered email")
	ISTAT_KEY=$(op read "op://Private/iStat Menus 6/license key")

	defaults write com.bjango.istatmenus _modelid -string "$(sysctl hw.model | sed 's/hw.model: //')"
	defaults write com.bjango.istatmenus installDateV6 -int "$(date -v +14d +%s)"
	/usr/libexec/PlistBuddy -c "Add :license6 dict" ~/Library/Preferences/com.bjango.istatmenus.plist
	/usr/libexec/PlistBuddy -c "Add :license6:email string $ISTAT_EMAIL" ~/Library/Preferences/com.bjango.istatmenus.plist
	/usr/libexec/PlistBuddy -c "Add :license6:serial string $ISTAT_KEY" ~/Library/Preferences/com.bjango.istatmenus.plist

	echo -e "✅ \033[1;32miStat Menus registered successfully.\033[0m"
else
	echo -e "✅ \033[1;32miStat Menus is already registered.\033[0m"
fi

# Charles
if [[ -z $(xmllint --xpath "string(//configuration/registrationConfiguration/key)" ~/Library/Preferences/com.xk72.charles.config) ]]; then
	echo -e "📝 \033[1;35mRegistering Charles...\033[0m"

	CHARLES_NAME=$(op read "op://Private/Charles/registered name")
	CHARLES_KEY=$(op read "op://Private/Charles/license key")
	# use printf instead of echo to avoid issues with newline characters in bash (not a problem with zsh)
	printf 'cd /configuration/registrationConfiguration/name\nset %s\nsave\n' "$CHARLES_NAME" | xmllint --shell ~/Library/Preferences/com.xk72.charles.config >/dev/null
	printf 'cd /configuration/registrationConfiguration/key\nset %s\nsave\n' "$CHARLES_KEY" | xmllint --shell ~/Library/Preferences/com.xk72.charles.config >/dev/null

	echo -e "✅ \033[1;32mCharles registered successfully.\033[0m"
else
	echo -e "✅ \033[1;32mCharles is already registered.\033[0m"
fi
