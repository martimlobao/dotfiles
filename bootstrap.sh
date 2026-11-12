#!/usr/bin/env bash

{ # Prevent script from running if partially downloaded

	set -euo pipefail

	DOTPATH=${HOME}/.dotfiles
	BRANCH=""
	CLEAN=false
	YES=false
	while getopts b:cy flag; do
		case "${flag}" in
		b) BRANCH=${OPTARG} ;;
		c) CLEAN=true ;;
		y) YES=true ;;
		*) echo "Invalid option: -${OPTARG}" && exit 1 ;;
		esac
	done

	echo -e "🥾 \033[1;34mBootstrapping dotfiles\033[0m"

	if [[ -z ${BRANCH} ]]; then
		BRANCH="main"
	fi
	# git on a fresh Mac is a stub that needs the Command Line Tools, so install them and wait for
	# the GUI installer to finish before cloning
	if [[ $(uname) == "Darwin" ]] && ! xcode-select -p &>/dev/null; then
		echo -e "🛠️  \033[1;33mInstalling Xcode Command Line Tools (complete the dialog to continue)...\033[0m"
		# Exits non-zero if an install is already pending, which is fine since we wait for it anyway.
		# Its output is left visible so a real failure explains the error below.
		xcode-select --install || true
		# The installer app stays open until the install finishes or is cancelled. Give it a few
		# seconds to launch, then wait for it to quit.
		installer="Install Command Line Developer Tools"
		for _ in {1..20}; do
			pgrep -qf "${installer}" && break
			sleep 0.5
		done
		while pgrep -qf "${installer}"; do
			sleep 2
		done
		if ! xcode-select -p &>/dev/null; then
			echo -e "❌ \033[1;31mCommand Line Tools were not installed (cancelled?). Rerun the bootstrap" \
				"to try again.\033[0m"
			exit 1
		fi
		echo -e "✅ \033[1;32mXcode Command Line Tools installed\033[0m"
	fi

	if [[ ! -d ${DOTPATH} ]]; then
		echo -e "📑 \033[1;33mCloning dotfiles on branch ${BRANCH}...\033[0m"
		git clone https://github.com/martimlobao/dotfiles.git --branch "${BRANCH}" "${DOTPATH}"
		echo -e "✅ \033[1;32mCloned Dotfiles to ${DOTPATH} on branch \"${BRANCH}\"\033[0m"
	else
		echo -e "✅ \033[1;34mDotfiles already downloaded to ${DOTPATH}, checking out branch \"${BRANCH}\"\033[0m"
		cd "${DOTPATH}"
		if [[ $(git status -s) ]] && [[ ${CLEAN} == true ]]; then
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
