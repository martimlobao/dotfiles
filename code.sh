#!/usr/bin/env bash

# Root is $DOTPATH if it exists, otherwise the directory of this script
root=$(realpath "${DOTPATH:-$(dirname "$(realpath "$0")")}")

# Source the bash_traceback.sh file
source "${root}/bash_traceback.sh"

###############################################################################
# Manage VSCode extensions                                                    #
###############################################################################

# Taken and modified from https://github.com/br3ndonland/dotfiles

# Check if the first argument is -y or --yes
auto_yes=false
for arg in "$@"; do
	if [[ ${arg} == "-y" ]] || [[ ${arg} == "--yes" ]]; then
		auto_yes=true
	fi
done

extensions_file="${root}/linkme/.config/code/extensions.txt"

export_extensions() {
	printf "\n📲 \033[1;34mExporting extensions from %s to extensions.txt...\033[0m\n\n" "$2"
	$1 --list-extensions >"${extensions_file}"
	printf "✅ \033[1;32mExtensions exported to extensions.txt\033[0m\n"
}

sync_extensions() {
	printf "\n📲 \033[1;34mSyncing extensions for %s...\033[0m\n\n" "$2"
	local installed to_remove=()

	# Get currently installed extensions
	mapfile -t installed < <($1 --list-extensions)

	# Install missing extensions
	while read -r extension; do
		if printf '%s\n' "${installed[@]}" | grep -q "^${extension}$"; then
			printf "✅ \033[1;32mExtension '%s' already installed.\033[0m\n" "${extension}"
		else
			printf "⬇️  \033[1;34mInstalling extension '%s'...\033[0m\n" "${extension}"
			$1 --install-extension "${extension}"
		fi
	done <"${extensions_file}"

	# Find extensions to remove
	for installed_extension in "${installed[@]}"; do
		if ! grep -q "^${installed_extension}$" "${extensions_file}"; then
			to_remove+=("${installed_extension}")
		fi
	done

	# If there are extensions to remove, ask for confirmation
	if [[ ${#to_remove[@]} -gt 0 ]]; then
		printf "\n❗️ \033[1;31mThe following extensions are not in extensions.txt:\033[0m\n"
		printf "  %s\n" "${to_remove[@]}"

		if [[ ${auto_yes} == false ]]; then
			read -rp $'❓ \033[1;31mDo you want to uninstall these extensions? (y/n)\033[0m ' choice
		else
			choice="y"
			printf "🔄 \033[1;35mAuto-confirming removal due to -y flag\033[0m\n"
		fi

		if [[ ${choice} == "y" ]]; then
			for extension in "${to_remove[@]}"; do
				printf "🗑️  \033[1;35mUninstalling extension '%s'...\033[0m\n" "${extension}"
				$1 --uninstall-extension "${extension}"
				printf "🚮 \033[1;35mUninstalled '%s'.\033[0m\n" "${extension}"
			done
		else
			printf "🆗 \033[1;35mNo extensions were uninstalled.\033[0m\n"
		fi
	else
		printf "✅ \033[1;32mAll installed extensions are present in extensions.txt.\033[0m\n"
	fi
}

# Parse arguments
editor="cursor" # default editor
action=""

for arg in "$@"; do
	case ${arg} in
	--export | --sync)
		action=${arg}
		;;
	-y | --yes)
		continue
		;;
	*)
		if [[ -n ${arg} ]]; then # Only set editor if arg is not empty
			editor=${arg}
		fi
		;;
	esac
done

if [[ -z ${action} ]]; then
	printf "\n❌ \033[1;31mError: Invalid action. Use --export or --sync\033[0m\n"
	printf "Usage: %s [editor] [--export|--sync] [-y|--yes]\n" "$0"
	exit 1
fi

# Get the friendly name for the editor
case ${editor} in
code) editor_name="Visual Studio Code" ;;
code-exploration) editor_name="Visual Studio Code - Exploration" ;;
code-insiders) editor_name="Visual Studio Code - Insiders" ;;
codium) editor_name="VSCodium" ;;
cursor) editor_name="Cursor" ;;
*)
	printf "\n❌ \033[1;31mError: Invalid editor specified.\033[0m\n"
	exit 1
	;;
esac

MACOS_BIN="/Applications/${editor}.app/Contents/Resources/app/bin"
if [[ "$(uname -s)" == "Darwin" ]] && [[ -d ${MACOS_BIN} ]]; then
	export PATH="${MACOS_BIN}:${PATH}"
fi

if ! type "${editor}" &>/dev/null; then
	printf "\n❌ \033[1;31mError: %s command not on PATH.\033[0m\n" "${editor}" >&2
	exit 1
else
	case ${action} in
	--export) export_extensions "${editor}" "${editor_name}" ;;
	--sync) sync_extensions "${editor}" "${editor_name}" ;;
	*)
		printf "\n❌ \033[1;31mError: Invalid action\033[0m\n"
		exit 1
		;;
	esac
fi
