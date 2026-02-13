#!/usr/bin/env bash

# Root is $DOTPATH if it exists, otherwise the parent directory of this script
root=$(realpath "${DOTPATH:-$(dirname "$(realpath "$0")")/../}")

# Source the bash_traceback.sh file
source "${root}/bash_traceback.sh"

###############################################################################
# Change default login shell to zsh                                          #
###############################################################################

zsh_path=$(command -v zsh)
if [[ -z ${zsh_path} ]]; then
	echo -e "❌ \033[1;31mError: zsh is not installed.\033[0m" >&2
	exit 1
fi

echo -e "🐚 \033[1;34mEnsuring default login shell is zsh...\033[0m"

# Get current default login shell (no sudo required)
current_shell=""
if [[ $(uname) == "Darwin" ]]; then
	current_shell=$(dscl . -read "/Users/${USER}" UserShell 2>/dev/null | sed 's/^UserShell: //')
else
	current_shell=$(getent passwd "${USER}" 2>/dev/null | cut -d: -f7)
fi
if [[ -n ${current_shell} ]] && [[ ${current_shell} == "${zsh_path}" ]]; then
	echo -e "✅ \033[1;32mDefault shell is already ${zsh_path}.\033[0m"
	exit 0
fi

if [[ ${1-} != "-y" ]] && [[ ${1-} != "--yes" ]]; then
	read -rp $'❓ \e[1;31mChange default login shell to zsh? (y/n)\e[0m ' CONFIRM
else
	CONFIRM="y"
fi

if [[ ! ${CONFIRM} =~ ^[Yy]$ ]]; then
	exit 0
fi

# Trigger GUI sudo prompt (Touch ID) before pipeline; pipeline sudo has no TTY
sudo -v

if ! grep -Fxq "${zsh_path}" /etc/shells 2>/dev/null; then
	echo -e "📝 \033[1;35mAdding ${zsh_path} to /etc/shells...\033[0m"
	if ! printf '%s\n' "${zsh_path}" | sudo tee -a /etc/shells >/dev/null; then
		echo -e "❌ \033[1;31mError: Failed to add zsh to /etc/shells.\033[0m" >&2
		exit 1
	fi
fi

# On macOS use dscl (with sudo) so Touch ID works; chsh prompts for password in terminal
if [[ $(uname) == "Darwin" ]]; then
	if [[ -n ${current_shell} ]]; then
		sudo dscl . -change "/Users/${USER}" UserShell "${current_shell}" "${zsh_path}"
	else
		sudo dscl . -create "/Users/${USER}" UserShell "${zsh_path}"
	fi
	echo -e "✅ \033[1;32mDefault shell changed to ${zsh_path}.\033[0m"
else
	if chsh -s "${zsh_path}"; then
		echo -e "🐣 \033[1;32mDefault shell changed to ${zsh_path}.\033[0m"
	else
		echo -e "❌ \033[1;31mError: chsh failed.\033[0m" >&2
		exit 1
	fi
fi
