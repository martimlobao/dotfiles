#!/usr/bin/env bash
set -euo pipefail
trap "echo 'Script was interrupted by the user.'; exit 1" INT

# Install oh-my-zsh if it isn't installed yet
if [ ! -d "$HOME/.oh-my-zsh" ]; then
	echo -e "⬇️  \033[1;34mInstalling oh-my-zsh...\033[0m"
	sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
else
	echo -e "✅  \033[1;32moh-my-zsh is already installed.\033[0m"
fi
