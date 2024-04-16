#!/usr/bin/env bash
set -euo pipefail
trap "echo 'Script was interrupted by the user.'; exit 1" INT

# Ask for the administrator password upfront and keep alive until script has finished
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

# Set computer name.
confirm_set "Set the name for this computer: " COMPUTERNAME
sudo scutil --set ComputerName "$COMPUTERNAME"
sudo scutil --set HostName "$COMPUTERNAME"
sudo scutil --set LocalHostName "$COMPUTERNAME"
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.smb.server NetBIOSName -string "$COMPUTERNAME"

# # Set up .gitconfig.private.
# GITCONFIGLOCAL=".gitconfig.private"
# rm -f $GITCONFIGLOCAL
# touch $GITCONFIGLOCAL
# printf "[user]\n" >> $GITCONFIGLOCAL
# confirm_set "Set your git author name: " NAME
# printf "\tname = %s\n" "$NAME" >> $GITCONFIGLOCAL
# confirm_set "Set your git author email: " EMAIL
# printf "\temail = %s\n" "$EMAIL" >> $GITCONFIGLOCAL
# printf "[github]\n" >> $GITCONFIGLOCAL
# confirm_set "Set your github username: " GITHUBUSER
# printf "\tuser = %s\n" "$GITHUBUSER" >> $GITCONFIGLOCAL

# op item get --fields="registered email" "iStat Menus 6"
# op read op://private/istat\ menus\ 6/registered\ email
# op item get --fields="license key" "iStat Menus 6"
# op read op://private/istat\ menus\ 6/license\ key

# copy all files from manual/ to ~/
cp -r manual/ ~/

# iStat Menus
if ! defaults read com.bjango.istatmenus license6 &> /dev/null; then
	echo -e "⬇️  \033[1;34mRegistering iStat Menus...\033[0m"
	defaults write com.bjango.istatmenus _modelid -string $(sysctl hw.model | sed 's/hw.model: //')
	defaults write com.bjango.istatmenus installDateV6 -int $(date -v +14d +%s)

	ISTAT_EMAIL=$(op item get --fields="registered email" "iStat Menus 6")
	ISTAT_KEY=$(op item get --fields="license key" "iStat Menus 6")
	/usr/libexec/PlistBuddy -c "Add :license6 dict" ~/Library/Preferences/com.bjango.istatmenus.plist
	/usr/libexec/PlistBuddy -c "Add :license6:email string $ISTAT_EMAIL" ~/Library/Preferences/com.bjango.istatmenus.plist
	/usr/libexec/PlistBuddy -c "Add :license6:serial string $ISTAT_KEY" ~/Library/Preferences/com.bjango.istatmenus.plist
	echo -e "✅  \033[1;32miStat Menus registered successfully.\033[0m"
else
	echo -e "✅  \033[1;32miStat Menus is already registered.\033[0m"
fi
