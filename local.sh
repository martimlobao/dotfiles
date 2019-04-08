#!/usr/bin/env bash

# Ask for the administrator password upfront and keep alive until script has finished
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

###############################################################################
# LOCAL SETTINGS AND VARIABLES                                                #
###############################################################################

confirm_set () {
	while [[ true ]]; do
		read -p "$1" $2
		read -p "Set to '${!2}'? (y/n) "
		if [[ $REPLY =~ ^[Yy]$ ]]; then
			break
		fi
	done
}

# Set computer name.
confirm_set "Set the name for this computer: " COMPUTERNAME
sudo scutil --set ComputerName $COMPUTERNAME
sudo scutil --set HostName $COMPUTERNAME
sudo scutil --set LocalHostName $COMPUTERNAME
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.smb.server NetBIOSName -string $COMPUTERNAME

# Set work or personal profile.
read -p "Is this a work computer? (y/n) " -n 1
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
	WORKPC=true
else
	WORKPC=false
fi
export WORKPC=$WORKPC

# Set up .gitconfig.private.
GITCONFIGLOCAL=".gitconfig.private"
rm -f $GITCONFIGLOCAL
touch $GITCONFIGLOCAL
printf "[user]\n" >> $GITCONFIGLOCAL
confirm_set "Set your git author name: " NAME
printf "\tname = $NAME\n" >> $GITCONFIGLOCAL
confirm_set "Set your git author email: " EMAIL
printf "\temail = $EMAIL\n" >> $GITCONFIGLOCAL
printf "[github]\n" >> $GITCONFIGLOCAL
confirm_set "Set your github username: " GITHUBUSER
printf "\tuser = $GITHUBUSER\n" >> $GITCONFIGLOCAL

# Setting up ssh.
echo "Generating SSH key..."
ssh-keygen
echo "Copying key to clipboard."
cat ~/.ssh/id_rsa.pub | pbcopy
echo "\n"
cat ~/.ssh/id_rsa.pub
echo "\n"
echo "Please add your SSH key to your Github and/or Bitbucket account."
sleep 2
open "https://github.com/settings/keys"
open "https://bitbucket.org/account/"

unset confirm_set;
