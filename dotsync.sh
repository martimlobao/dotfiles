#!/usr/bin/env bash

# Source the bash_traceback.sh file
source "$(dirname "$0")/bash_traceback.sh"

###############################################################################
# UPDATE DOTFILES                                                             #
###############################################################################


function dotlink() {
	find "linkme" -type d -mindepth 1 | sed "s|^linkme/||" | \
		while read -r dir; do mkdir -p "$HOME/$dir"; done
	find "linkme" -type f -not -name '.DS_Store' | sed "s|^linkme/||" | \
		while read -r file; do
			echo -e "\033[1;32m🔗 Linked $(pwd)/linkme/$file -> $HOME/$file\033[0m"
			ln -fvns "$(pwd)/linkme/$file" "$HOME/$file" &> /dev/null;
		done
}

function dotunlink() {
	rsync -av --exclude='.DS_Store' linkme/ "$HOME" | \
		grep -v "building file list ... done" | \
		awk '/^$/ { exit } !/\/$/ { printf "\033[1;32m🔙 Restored %s\033[0m\n", $0; }'
}

# Copy all files from copyme/ to $HOME
if [ "${1:-}" == "unlink" ]; then
	echo -e "\033[1;34m📋 Restoring dotfiles...\033[0m"
	dotunlink;
else
	echo -e "\033[1;34m🔗 Linking dotfiles...\033[0m"
	if [[ "${1:-}" != "-y" ]] && [[ "${1:-}" != "--yes" ]]; then
		read -rp $'❓ \e[1;31mOverwrite existing dotfiles with symlinks to stored dotfiles? (y/n)\e[0m ' LINK
	else
		LINK="y"
	fi

	if [[ $LINK =~ ^[Yy]$ ]]; then
		dotlink;
	fi
fi

# shellcheck source=/dev/null
source "$HOME"/.zprofile
