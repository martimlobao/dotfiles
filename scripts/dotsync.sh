#!/usr/bin/env bash

# Root is $DOTPATH if it exists, otherwise the parent directory of this script
root=$(realpath "${DOTPATH:-$(dirname "$(realpath "$0")")/../}")

# Source the bash_traceback.sh file
source "${root}/bash_traceback.sh"

set -o pipefail

###############################################################################
# Update dotfiles                                                             #
###############################################################################

function dotlink() {
	local linkme_root="${root}/linkme"

	if ! find "${linkme_root}" -mindepth 1 -type d -print0 |
		while IFS= read -r -d '' dir; do
			relative_dir="${dir#"${linkme_root}/"}"
			mkdir -p "${HOME}/${relative_dir}" || exit 1
		done; then
		echo -e "❌ \033[1;31mFailed to create directories from linkme/.\033[0m" >&2
		return 1
	fi

	if ! find "${linkme_root}" \( -type f -o -type l \) -not -name '.DS_Store' -print0 |
		while IFS= read -r -d '' file; do
			relative_file="${file#"${linkme_root}/"}"
			echo -e "\033[1;32m✅ Linked linkme/${relative_file} -> ~/${relative_file}\033[0m"
			ln -fvns "${linkme_root}/${relative_file}" "${HOME}/${relative_file}" 1>/dev/null || exit 1
		done; then
		echo -e "❌ \033[1;31mFailed to link files from linkme/.\033[0m" >&2
		return 1
	fi
}

function dotunlink() {
	if ! rsync -av --exclude='.DS_Store' "${root}/linkme/" "${HOME}" |
		awk '/building file list ... done/ { next } /^$/ { exit } !/\/$/ { printf "\033[1;32m🔙 Restored %s\033[0m\n", $0; }'; then
		echo -e "❌ \033[1;31mFailed to restore files from linkme/.\033[0m" >&2
		return 1
	fi
}

# Copy all files from copyme/ to $HOME
if [[ ${1-} == "unlink" ]]; then
	echo -e "📋 \033[1;34mRestoring dotfiles...\033[0m"
	if ! dotunlink; then
		exit 1
	fi
else
	echo -e "🔗 \033[1;34mLinking dotfiles...\033[0m"
	if [[ ${1-} != "-y" ]] && [[ ${1-} != "--yes" ]]; then
		read -rp $'❓ \e[1;31mOverwrite existing dotfiles with symlinks to stored dotfiles? (y/n)\e[0m ' LINK
	else
		LINK="y"
	fi

	if [[ ${LINK} =~ ^[Yy]$ ]]; then
		if ! dotlink; then
			exit 1
		fi
		# 1Password needs the permissions to be set to 700
		chmod 700 "${HOME}/.config/op"
	fi
fi

# shellcheck source=/dev/null
source "${HOME}/.zprofile"
