#!/usr/bin/env bash

# Root is $DOTPATH if it exists, otherwise the parent directory of this script
root=$(realpath "${DOTPATH:-$(dirname "$(realpath "$0")")/../}")

# Source the bash_traceback.sh file
source "${root}/bash_traceback.sh"

###############################################################################
# Change default login shell to zsh                                          #
###############################################################################

if [[ ${1-} != "-y" ]] && [[ ${1-} != "--yes" ]]; then
	read -rp $'❓ \e[1;31mChange default login shell to zsh? (y/n)\e[0m ' CONFIRM
else
	CONFIRM="y"
fi

if [[ ! ${CONFIRM} =~ ^[Yy]$ ]]; then
	exit 0
fi

zsh_path=$(command -v zsh)
if [[ -z ${zsh_path} ]]; then
	echo -e "\033[1;31mError: zsh is not installed.\033[0m" >&2
	exit 1
fi

if ! grep -Fxq "${zsh_path}" /etc/shells 2>/dev/null; then
	echo -e "\033[1;33mAdding ${zsh_path} to /etc/shells...\033[0m"
	if ! printf '%s\n' "${zsh_path}" | sudo tee -a /etc/shells >/dev/null; then
		echo -e "\033[1;31mError: Failed to add zsh to /etc/shells.\033[0m" >&2
		exit 1
	fi
fi

if chsh -s "${zsh_path}"; then
	echo -e "\033[1;32mDefault shell changed to ${zsh_path}.\033[0m"
else
	echo -e "\033[1;31mError: chsh failed.\033[0m" >&2
	exit 1
fi
