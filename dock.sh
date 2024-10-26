#!/usr/bin/env bash
set -o errexit  # stop the script each time a command fails
set -o nounset  # stop if you attempt to use an undef variable

function bash_traceback() {
	local lasterr="$?"
	set +o xtrace
	local code="-1"
	local bash_command=${BASH_COMMAND}
	echo "Error in ${BASH_SOURCE[1]}:${BASH_LINENO[0]} ('$bash_command' exited with status $lasterr)" >&2
	if [ ${#FUNCNAME[@]} -gt 2 ]; then
		# Print out the stack trace described by $function_stack
		echo "Traceback of ${BASH_SOURCE[1]} (most recent call last):" >&2
		for ((i=0; i < ${#FUNCNAME[@]} - 1; i++)); do
		local funcname="${FUNCNAME[$i]}"
		[ "$i" -eq "0" ] && funcname=$bash_command
		echo -e "  ${BASH_SOURCE[$i+1]}:${BASH_LINENO[$i]}\\t$funcname" >&2
		done
	fi
	echo "Exiting with status ${code}" >&2
	exit "${code}"
}

# provide an error handler whenever a command exits nonzero
trap 'bash_traceback' ERR

# propagate ERR trap handler functions, expansions and subshells
set -o errtrace

###############################################################################
# FUNCTIONS FOR MANIPULATING MACOS DOCK                                       #
###############################################################################
function add_app_to_dock {
	# adds an application to macOS Dock
	# usage: add_app_to_dock "Application Name"
	# example add_app_to_dock "Terminal"
	app_name="${1}"
	launchservices_path="/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister"
	app_path=$(${launchservices_path} -dump | grep -o "/.*${app_name}.app" | grep -v -E "Backups|Caches|TimeMachine|Temporary|/Volumes/${app_name}" | uniq | sort | head -n1)
	if open -Ra "${app_path}"; then
		defaults write com.apple.dock persistent-apps -array-add "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>${app_path}</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
		echo "$app_path added to the Dock."
	else
		echo "ERROR: $1 not found." 1>&2
	fi
}

function add_folder_to_dock {
	# adds a folder to macOS Dock
	# usage: add_folder_to_dock "Folder Path" -s n -d n -v n
	# example: add_folder_to_dock "~/Downloads" -d 0 -s 2 -v 1
	# key:
	# -s or --sortby
	# 1 -> Name
	# 2 -> Date Added
	# 3 -> Date Modified
	# 4 -> Date Created
	# 5 -> Kind
	# -d or --displayas
	# 0 -> Stack
	# 1 -> Folder
	# -v or --viewcontentas
	# 0 -> Automatic
	# 1 -> Fan
	# 2 -> Grid
	# 3 -> List
	folder_path="${1}"
	sortby="1"
	displayas="0"
	viewcontentas="0"
	while [[ "$#" -gt 0 ]]
	do
		case $1 in
			-s|--sortby)
			if [[ $2 =~ ^[1-5]$ ]]; then
				sortby="${2}"
			fi
			;;
			-d|--displayas)
			if [[ $2 =~ ^[0-1]$ ]]; then
				displayas="${2}"
			fi
			;;
			-v|--viewcontentas)
			if [[ $2 =~ ^[0-3]$ ]]; then
				viewcontentas="${2}"
			fi
			;;
		esac
		shift
	done

	if [ -d "$folder_path" ]; then
		defaults write com.apple.dock persistent-others -array-add "<dict>
				<key>tile-data</key> <dict>
					<key>arrangement</key> <integer>${sortby}</integer>
					<key>displayas</key> <integer>${displayas}</integer>
					<key>file-data</key> <dict>
						<key>_CFURLString</key> <string>file://${folder_path}</string>
						<key>_CFURLStringType</key> <integer>15</integer>
					</dict>
					<key>file-type</key> <integer>2</integer>
					<key>showas</key> <integer>${viewcontentas}</integer>
				</dict>
				<key>tile-type</key> <string>directory-tile</string>
			</dict>"
		echo "$folder_path added to the Dock."
	else
		echo "ERROR: $folder_path not found." 1>&2
	fi
}

function add_spacer_to_dock {
	# adds an empty space to macOS Dock
	defaults write com.apple.dock persistent-apps -array-add '{"tile-type"="small-spacer-tile";}'
}

function clear_dock {
	# removes all persistent icons from macOS Dock
	if [ "$(defaults read com.apple.dock persistent-apps | wc -l)" -gt 0 ]; then
		defaults write com.apple.dock persistent-apps -array
	fi
	if [ "$(defaults read com.apple.dock persistent-others | wc -l)" -gt 0 ]; then
		defaults write com.apple.dock persistent-others -array
	fi
	killall Dock
}

function reset_launchpad {
	# resets Launchpad so that all apps appear in their default order
	defaults write com.apple.dock ResetLaunchPad -bool true
}


###############################################################################
# CONFIGURE MACOS DOCK                                                        #
###############################################################################
reset_launchpad
clear_dock

add_app_to_dock "Arc"
add_app_to_dock "Obsidian"
add_app_to_dock "Todoist"
add_app_to_dock "Linear"
add_app_to_dock "Slack"
add_app_to_dock "Visual Studio Code"
add_app_to_dock "Cursor"
add_app_to_dock "Warp"
add_app_to_dock "System Settings"
add_folder_to_dock ~/Downloads --sortby 2 --displayas 1 --viewcontentas 1

killall Dock
