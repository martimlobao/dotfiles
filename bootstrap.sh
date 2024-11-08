#!/usr/bin/env bash

{ # Prevent script from running if partially downloaded

	set -euo pipefail

	DOTPATH=${HOME}/.dotfiles
	BRANCH=${1-}

	echo -e "\033[1;34m🥾 Bootstrapping dotfiles\033[0m"

	if [[ ! -d ${DOTPATH} ]]; then
		if [[ -z ${BRANCH} ]]; then
			git clone https://github.com/martimlobao/dotfiles.git "${DOTPATH}"
			echo -e "\033[1;32m✅ Cloned ${DOTPATH}\033[0m"
		else
			git clone https://github.com/martimlobao/dotfiles.git --branch "${BRANCH}" "${DOTPATH}"
			echo -e "\033[1;32m✅ Cloned ${DOTPATH} on branch ${BRANCH}\033[0m"
		fi
	else
		if [[ -z ${BRANCH} ]]; then
			echo -e "\033[1;34m✅ Dotfiles already downloaded to ${DOTPATH}\033[0m"
		else
			cd "${DOTPATH}"
			git stash
			git checkout "${BRANCH}"
			git pull origin "${BRANCH}"
			echo -e "\033[1;34m✅ Dotfiles already downloaded to ${DOTPATH} on branch ${BRANCH}\033[0m"
		fi
	fi

	cd "${DOTPATH}"

	if [[ ${1-} == "--yes" ]] || [[ ${1-} == "-y" ]]; then
		./run.sh -y
	else
		./run.sh
	fi

} # Prevent script from running if partially downloaded
