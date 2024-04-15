#!/usr/bin/env bash

###############################################################################
# UPDATE DOTFILES                                                             #
###############################################################################

cd "$(dirname "${BASH_SOURCE}")" || exit 1;

git pull origin main;

# Sync dotfiles (excludes folders, .sh files, .md files, and git files)
function bootstrap() {
	rsync --exclude "*.sh" \
		--exclude "*.md" \
		--exclude ".DS_Store" \
		--exclude ".gitignore" \
		-f"- */" \
		-avh --no-perms . ~;
	source ~/.bash_profile;
}

if [ "$1" == "--force" ] || [ "$1" == "-f" ]; then
	bootstrap;
else
	read -rp "This may overwrite existing files in your home directory. Are you sure? (y/n) " -n 1;
	echo "";
	if [[ $REPLY =~ ^[Yy]$ ]]; then
		bootstrap;
	fi;
fi;
unset bootstrap;
