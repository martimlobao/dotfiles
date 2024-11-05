#!/usr/bin/env bash

set -eu

{ # Prevent script from running if partially downloaded

DOTPATH=$HOME/.dotfiles

BRANCH="${1:-main}"
echo "Bootstrap with branch '${BRANCH}'"

if [ ! -d "$DOTPATH" ]; then
	git clone -b "$BRANCH" https://github.com/martimlobao/dotfiles.git "$DOTPATH"
else
	echo "$DOTPATH already downloaded. Updating..."
	cd "$DOTPATH"
	git stash
	git checkout "$BRANCH"
	git pull origin "$BRANCH"
	echo
fi

cd "$DOTPATH"

./run.sh

} # Prevent script from running if partially downloaded
