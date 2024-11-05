#!/usr/bin/env bash

set -eu

{ # Prevent script from running if partially downloaded

DOTPATH=$HOME/.dotfiles

echo -e "\033[1;34m🥾 Bootstrapping dotfiles\033[0m"

if [ ! -d "$DOTPATH" ]; then
	git clone https://github.com/martimlobao/dotfiles.git "$DOTPATH"
	echo -e "\033[1;32m✅ Cloned $DOTPATH\033[0m"
else
	echo -e "\033[1;34m✅ Dotfiles already downloaded to $DOTPATH\033[0m"
fi

cd "$DOTPATH"

if [[ "${1:-}" == "--yes" ]] || [[ "${1:-}" == "-y" ]]; then
	./run.sh -y
else
	./run.sh
fi

} # Prevent script from running if partially downloaded
