#!/usr/bin/env bash

###############################################################################
# UPDATE DOTFILES                                                             #
###############################################################################

cd "$(dirname "${BASH_SOURCE}")";

git pull origin master;

function bootstrap() {
	rsync --exclude ".git/" \
		--exclude ".DS_Store" \
		--exclude ".gitignore" \
		--exclude "README.md" \
		--exclude "LICENSE-MIT.txt" \
		--exclude "*.sh" \
		-avh --no-perms . ~;
	source ~/.bash_profile;
}

if [ "$1" == "--force" -o "$1" == "-f" ]; then
	bootstrap;
else
	read -p "This may overwrite existing files in your home directory. Are you sure? (y/n) " -n 1;
	echo "";
	if [[ $REPLY =~ ^[Yy]$ ]]; then
		bootstrap;
	fi;
fi;
unset bootstrap;
