#!/usr/bin/env bash

{ # Prevent script from running if partially downloaded

	set -euo pipefail

	DOTPATH=${HOME}/.dotfiles
	BRANCH=""
	YES=false
	while getopts b:y flag; do
		case "${flag}" in
		b) BRANCH=${OPTARG} ;;
		y) YES=true ;;
		*) echo "Invalid option: -${OPTARG}" && exit 1 ;;
		esac
	done

	# intentional error for testing
	false
	echo "This should not be printed"
	exit 1

	echo -e "🥾 \033[1;34mBootstrapping dotfiles\033[0m"

	if [[ -z ${BRANCH} ]]; then
		BRANCH="main"
	fi
	if [[ ! -d ${DOTPATH} ]]; then
		echo -e "📑 \033[1;33mCloning dotfiles on branch ${BRANCH}...\033[0m"
		git clone https://github.com/martimlobao/dotfiles.git --branch "${BRANCH}" "${DOTPATH}"
		echo -e "✅ \033[1;32mCloned Dotfiles to ${DOTPATH} on branch \"${BRANCH}\"\033[0m"
	else
		echo -e "✅ \033[1;34mDotfiles already downloaded to ${DOTPATH}, checking out branch \"${BRANCH}\"\033[0m"
		cd "${DOTPATH}"
		if [[ $(git status -s) ]]; then
			echo -e "🔄 \033[1;33mStashing existing changes...\033[0m"
			git stash save "stash created automatically on $(date) by bootstrap.sh"
		fi
		git checkout "${BRANCH}"
		git pull --ff-only origin "${BRANCH}"
	fi

	cd "${DOTPATH}"

	if [[ ${YES} == true ]]; then
		./run.sh -y
	else
		./run.sh
	fi

} # Prevent script from running if partially downloaded
