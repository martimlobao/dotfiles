#!/usr/bin/env bash

# Root is $DOTPATH if it exists, otherwise the directory of this script
root=$(realpath "${DOTPATH:-$(dirname "$(realpath "$0")")}")

# Source the bash_traceback.sh file
source "${root}/bash_traceback.sh"

###############################################################################
# Update dotfiles                                                             #
###############################################################################

function dotlink() {
	find "linkme" -type d -mindepth 1 | sed "s|^linkme/||" |
		while read -r dir; do mkdir -p "${HOME}/${dir}"; done
	find "linkme" -type f -not -name '.DS_Store' | sed "s|^linkme/||" |
		while read -r file; do
			echo -e "\033[1;32m✅ Linked linkme/${file} -> ~/${file}\033[0m"
			ln -fvns "${root}/linkme/${file}" "${HOME}/${file}" 1>/dev/null
		done
}

function dotunlink() {
	rsync -av --exclude='.DS_Store' linkme/ "${HOME}" |
		grep -v "building file list ... done" |
		awk '/^$/ { exit } !/\/$/ { printf "\033[1;32m🔙 Restored %s\033[0m\n", $0; }'
}

# Copy all files from copyme/ to $HOME
if [[ ${1-} == "unlink" ]]; then
	echo -e "📋 \033[1;34mRestoring dotfiles...\033[0m"
	dotunlink
else
	echo -e "🔗 \033[1;34mLinking dotfiles...\033[0m"
	if [[ ${1-} != "-y" ]] && [[ ${1-} != "--yes" ]]; then
		read -rp $'❓ \e[1;31mOverwrite existing dotfiles with symlinks to stored dotfiles? (y/n)\e[0m ' LINK
	else
		LINK="y"
	fi

	if [[ ${LINK} =~ ^[Yy]$ ]]; then
		dotlink
		# 1Password needs the permissions to be set to 700
		chmod 700 "${HOME}/.config/op"
	fi
fi

# shellcheck source=/dev/null
source "${HOME}/.zprofile"
