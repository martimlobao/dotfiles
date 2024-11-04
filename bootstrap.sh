#!/usr/bin/env bash

###############################################################################
# UPDATE DOTFILES                                                             #
###############################################################################

cd "$(dirname "${BASH_SOURCE:-$0}")" || exit 1;

function dotlink() {
	find "linkme" -type d -mindepth 1 | sed "s|^linkme/||" | while read -r dir; do mkdir -p "$HOME/$dir"; done
	find "linkme" -type f -not -name '.DS_Store' | sed "s|^linkme/||" | while read -r file; do ln -fvns "$(pwd)/linkme/$file" "$HOME/$file"; done
}

function dotunlink() {
	rsync -av --exclude='.DS_Store' linkme/ "$HOME" | \
		grep -v "building file list ... done" | \
		awk '/^$/ { exit } !/\/$/ { print "Restored " $0 }'
}

if [ "$1" == "unlink" ]; then
	dotunlink;
elif [ "$1" == "--force" ] || [ "$1" == "-f" ]; then
	dotlink;
else
	read -rp $'❓ \e[1;31mThis may overwrite existing files in your home directory. Are you sure? (y/n)\e[0m ' REPLY
	if [[ $REPLY =~ ^[Yy]$ ]]; then
		dotlink;
	fi;
fi;

# shellcheck source=/dev/null
source "$HOME"/.zprofile
