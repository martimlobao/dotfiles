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

while [[ true ]]; do
	read -p "Is this a (w)ork computer or a (p)ersonal computer? " PCTYPE
	if [[ $PCTYPE =~ ^[wp]$ ]]; then
		break
	else
		echo "Unrecognized response '$PCTYPE'"
	fi
done
echo $PCTYPE

# Setting up .gitconfig.local
# Only run if file does not already exist?
GITCONFIGLOCAL="~/.gitconfig.local"
touch $GITCONFIGLOCAL

printf "[user]" > $GITCONFIGLOCAL
confirm_set "Set your git author name: " NAME
printf "\tname = $NAME" > $GITCONFIGLOCAL
confirm_set "Set your git author email: " EMAIL
printf "\temail = $EMAIL" > $GITCONFIGLOCAL

printf "[github]" > $GITCONFIGLOCAL
confirm_set "Set your github username: " GITHUBUSER
printf "\tuser = $GITHUBUSER" > $GITCONFIGLOCAL


open "https://github.com/settings/tokens"
confirm_set "Set your github token: " GITHUBTOKEN
printf "\ttoken = $GITHUBTOKEN" > $GITCONFIGLOCAL

# https://atom.io/packages/sync-settings
confirm_set "Set your Atom 'Sync Settings' package token: " ATOMGISTID
ATOMGISTID="eeee555"
printf "\tatomgistid = $ATOMGISTID" > $GITCONFIGLOCAL

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
