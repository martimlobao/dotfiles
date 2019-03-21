#!/usr/bin/env bash

# Ask for the administrator password upfront and keep alive until script has finished
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

###############################################################################
# LOCAL SETTINGS AND ENVIRONMENT VARIABLES                                    #
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

read -p "Is this a work computer? (y/n) " -n 1;
echo "";
if [[ $REPLY =~ ^[Yy]$ ]]; then
	WORKPC=true;
fi;

# Setting up .gitconfig.local
# Only run if file does not already exist?
GITCONFIGLOCAL="$HOME/.gitconfig.local"
touch $GITCONFIGLOCAL

printf "[user]\n" >> $GITCONFIGLOCAL
confirm_set "Set your git author name: " NAME
printf "\tname = $NAME\n" >> $GITCONFIGLOCAL
confirm_set "Set your git author email: " EMAIL
printf "\temail = $EMAIL\n" >> $GITCONFIGLOCAL

printf "[github]\n" >> $GITCONFIGLOCAL
confirm_set "Set your github username: " GITHUBUSER
printf "\tuser = $GITHUBUSER\n" >> $GITCONFIGLOCAL


open "https://github.com/settings/tokens"
confirm_set "Set your github token: " GITHUBTOKEN
printf "\ttoken = $GITHUBTOKEN\n" >> $GITCONFIGLOCAL

# https://atom.io/packages/sync-settings
confirm_set "Set your Atom 'Sync Settings' package token: " ATOMGISTID
ATOMGISTID="eeee555"
printf "\tatomgistid = $ATOMGISTID\n" >> $GITCONFIGLOCAL

echo "Generating SSH key..."
ssh-keygen
echo "Copying key to clipboard."
cat ~/.ssh/id_rsa.pub | pbcopy
echo "\n"
cat ~/.ssh/id_rsa.pub
echo "\n"
echo "Please add your SSH key to your Github account."
open "https://github.com/settings/keys"
echo "Please add your SSH key to your Bitbucket account."
open "https://bitbucket.org/account/"

confirm_set "Set your computer name: " COMPUTERNAME
echo $COMPUTERNAME

unset confirm_set;
