#!/usr/bin/env bash

# Source the bash_traceback.sh file
source "$(dirname "$0")/bash_traceback.sh"

###############################################################################
# INSTALL APPS AND PACKAGES                                                   #
###############################################################################

echo -e "📲 \033[1;36mInstalling apps and packages...\033[0m"

# Initialize arrays to store installed apps
installed_casks=()
installed_formulas=()
installed_mas=()
installed_uv=()

# Populate the arrays with installed apps
populate_installed_apps() {
	while IFS= read -r app; do
		installed_casks+=("$app")
	done < <(brew list --cask)

	while IFS= read -r app; do
		installed_formulas+=("$app")
	done < <(brew list --formula)

	while IFS= read -r app; do
		installed_mas+=("$app")
	done < <(mas list | cut -d' ' -f1)

	while IFS= read -r app; do
		installed_uv+=("$app")
	done < <(uv tool list | cut -d' ' -f1)
}

# Function to check if an item is in an array
in_array() {
	local needle="$1"
	shift
	local item
	for item; do
		[[ "$item" == "$needle" ]] && return 0
	done
	return 1
}

# Install function that uses the correct command based on the installation method
install () {
	local app="$1"
	local app_name="${app##*/}"  # Extract the part after the last slash
	local method="$2"
	local cmd=""
	local is_installed=false

	case "$method" in
		"cask")
			cmd="brew install --cask"
			in_array "$app_name" "${installed_casks[@]}" && is_installed=true
			;;
		"formula")
			cmd="brew install --formula"
			in_array "$app_name" "${installed_formulas[@]}" && is_installed=true
			;;
		"mas")
			if mas list | grep -q "$app "; then
				is_installed=true
				app_name=$(mas list | grep "$app " | sed -E 's/.*[0-9]+[[:space:]]+(.*)[[:space:]]+\(.*/\1/' | sed -E 's/[[:space:]]*$//')
			else
				app_name=$(mas info "$app" | head -n 1 | sed -E 's/(.*)[[:space:]]+[0-9\.]+ \[.*\]/\1/')
				cmd="mas install"
			fi
			;;
		"uv")
			cmd="uv tool install"
			in_array "$app" "${installed_uv[@]}" && is_installed=true
			;;
		*)
			echo -e "❌ \033[1;31mUnknown installation method: $method for $app_name\033[0m"
			return 1
			;;
	esac

	if ! $is_installed; then
		echo -e "⬇️ \033[1;34mInstalling ${app_name}...\033[0m"
		if ! $cmd "$app"; then
			echo -e "❌ \033[1;31mFailed to install $app_name. Please check manually.\033[0m"
			return 1
		fi
	else
		echo -e "✅ \033[1;32m${app_name} is already installed.\033[0m"
	fi
}

brew_sync() {
	local toml_apps
	toml_apps=$(yq eval 'to_entries | map(.value | to_entries | map(select(.value == "cask" or .value == "formula") | .key)) | flatten | .[]' apps.toml)
	toml_apps=$(echo "$toml_apps" | sed -E 's|.*/||')  # get name from tapped apps (slashes in name)

	local missing_formulae
	missing_formulae=$(comm -23 <(brew leaves | sort) <(echo "$toml_apps" | sort))
	local missing_casks
	missing_casks=$(comm -23 <(brew list --cask | sort) <(echo "$toml_apps" | sort))
	local missing_apps
	missing_apps=$(echo -e "$missing_formulae\n$missing_casks" | sort -u)

	if [[ -n "$missing_apps" ]]; then
		echo -e "❗️ \033[1;31mThe following Homebrew-installed formulae and casks are missing from apps.toml:\033[0m"
		# shellcheck disable=SC2001
		echo "$missing_formulae" | sed 's/^/  /'
		  # shellcheck disable=SC2001
		echo "$missing_casks" | sed 's/^/  /'
		read -rp $'❓ \e[1;31mDo you want to uninstall these apps? (y/n)\e[0m ' choice
		if [[ "$choice" == "y" ]]; then
			for app in $missing_apps; do
				brew uninstall "$app"
				echo -e "🚮 \033[1;35mUninstalled $app.\033[0m"
			done
		else
			echo -e "🆗 \033[1;35mNo apps were uninstalled.\033[0m"
		fi
	else
		echo -e "✅ \033[1;32mAll Homebrew-installed formulae and casks are present in apps.toml.\033[0m"
	fi
}

uv_sync() {
	local toml_apps
	toml_apps=$(yq eval 'to_entries | map(.value | to_entries | map(select(.value == "uv") | .key)) | flatten | .[]' apps.toml)

	local missing_uv_apps
	missing_uv_apps=$(comm -23 <(uv tool list | awk '{print $1}' | grep -v '^-*$' | sort) <(echo "$toml_apps" | sort))

	if [[ -n "$missing_uv_apps" ]]; then
		echo -e "❗️ \033[1;31mThe following uv-installed apps are missing from apps.toml:\033[0m"
		  # shellcheck disable=SC2001
		echo "$missing_uv_apps" | sed 's/^/  /'
		read -rp $'❓ \e[1;31mDo you want to uninstall these apps? (y/n \e[0m ' choice
		if [[ "$choice" == "y" ]]; then
			for app in $missing_uv_apps; do
				uv tool uninstall "$app"
				echo -e "🚮 \033[1;35mUninstalled $app.\033[0m"
			done
		else
			echo -e "🆗 \033[1;35mNo apps were uninstalled.\033[0m"
		fi
	else
		echo -e "✅ \033[1;32mAll uv-installed apps are present in apps.toml.\033[0m"
	fi
}

mas_sync() {
	local toml_apps
	toml_apps=$(yq eval 'to_entries | map(.value | to_entries | map(select(.value == "mas") | .key)) | flatten | .[]' apps.toml)

	local installed_mas_apps
	installed_mas_apps=$(mas list | sed -E 's/^([0-9]+)[[:space:]]+(.*)[[:space:]]+\(.*/\1 \2/' | sort)

	# `-A` requires bash 4+, can't use Apple-provided bash which is 3.2
	declare -A missing_mas_apps=()  # Ensure it's initialized as an empty associative array

	while read -r id name; do
		if ! echo "$toml_apps" | grep -q "^$id$"; then
			missing_mas_apps["$id"]="$name"  # Store ID as key and app name as value
		fi
	done <<< "$installed_mas_apps"

	if [[ ${#missing_mas_apps[@]} -gt 0 ]]; then
		echo -e "❗️ \033[1;31mThe following Mac App Store apps are missing from apps.toml:\033[0m"
		for id in "${!missing_mas_apps[@]}"; do
			echo -e "  ${missing_mas_apps[$id]} ($id)"
		done
		read -rp $'❓ \e[1;31mDo you want to uninstall these apps? (y/n)\e[0m ' choice
		if [[ "$choice" == "y" ]]; then
			for id in "${!missing_mas_apps[@]}"; do
				name="${missing_mas_apps[$id]}"
				# mas uninstall doesn't actually work so fall back to telling user to uninstall manually
				if ! mas uninstall "$id"; then
					echo -e "❌ \033[1;31mFailed to uninstall $name ($id). Please uninstall it manually.\033[0m"
				else
					echo -e "🚮 \033[1;35mUninstalled $name ($id).\033[0m"
				fi
			done
		else
			echo -e "🆗 \033[1;35mNo apps were uninstalled.\033[0m"
		fi
	else
		echo -e "✅ \033[1;32mAll Mac App Store apps are present in apps.toml.\033[0m"
	fi
}

# Ensure yq is installed
if ! command -v yq &> /dev/null; then
	brew install yq
fi

# Populate the arrays with installed apps
populate_installed_apps

# Use yq to parse the TOML file and store the output in a variable
# shellcheck disable=2016
parsed_toml=$(yq e 'to_entries | .[] | .key as $category | .value | to_entries[] | [$category, .key, .value] | @tsv' apps.toml)

# Install apps from each category in the apps.toml file
current_category=""
echo "$parsed_toml" | while IFS=$'\t' read -r category app method; do
	if [[ "$category" != "$current_category" ]]; then
		suffix=$([[ "$category" == *s ]] && echo "" || echo " apps")
		echo -e "\n📦 \033[1;35mInstalling ${category}${suffix}...\033[0m"
		current_category="$category"
	fi
	install "$app" "$method"
done

echo -e "\n🔄 \033[1;35mSyncing installed apps to apps.toml...\033[0m"
brew_sync
uv_sync
mas_sync

# Update Homebrew and installed formulas, casks and uv apps
echo -e "\n🔼 \033[1;35mUpdating existing apps and packages...\033[0m"
brew update
brew upgrade
uv tool upgrade --all
read -rp $'❓ \e[1;31mUpdate Mac App Store apps (may be slightly buggy)? (y/n)\e[0m ' choice
if [[ "$choice" == "y" ]]; then
	mas upgrade
fi

# Remove outdated versions from the cellar
brew cleanup
