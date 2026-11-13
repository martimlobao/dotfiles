#!/usr/bin/env bash

# Root is $DOTPATH if it exists, otherwise the parent directory of this script
root=$(realpath "${DOTPATH:-$(dirname "$(realpath "$0")")/../}")

# Source the bash_traceback.sh file
source "${root}/bash_traceback.sh"

###############################################################################
# Helpers                                                                     #
###############################################################################

# What to restart (Finder, Dock, menubar) or "logout" when a setting changes; set per section
on_change=""
# Space-separated list of the on_change targets that had at least one setting updated
changed=""

function already_set {
	echo -e "✅ \033[1;32mAlready set: ${1}\033[0m"
}

function updated {
	echo -e "🔧 \033[1;33mUpdated: ${1}\033[0m"
	changed="${changed} ${on_change}"
}

function set_default {
	# writes a scalar preference only if it differs from the current value
	# usage: set_default [-currentHost] <domain> <key> <bool|int|float|string> <value>
	# example: set_default com.apple.dock autohide bool true
	local host=""
	if [[ ${1} == "-currentHost" ]]; then
		host="${1}"
		shift
	fi
	local domain="${1}" key="${2}" type="${3}" value="${4}"
	local label="${host:+${host} }${domain} ${key} = ${value}"
	# `defaults read` prints booleans as 1/0
	local expected="${value}"
	if [[ ${type} == "bool" && ${value} == "true" ]]; then
		expected=1
	elif [[ ${type} == "bool" ]]; then
		expected=0
	fi
	local current
	current=$(defaults ${host:+"${host}"} read "${domain}" "${key}" 2>/dev/null || true)
	if [[ ${current} == "${expected}" ]]; then
		already_set "${label}"
	else
		defaults ${host:+"${host}"} write "${domain}" "${key}" "-${type}" "${value}"
		updated "${label}"
	fi
}

function set_collection {
	# writes an array preference only if its whitespace-stripped `defaults read` output differs
	# usage: set_collection <domain> <key> <expected output> <defaults write args...>
	# example: set_collection NSGlobalDomain AppleLanguages '("en-US")' -array en-US
	local domain="${1}" key="${2}" expected="${3}"
	shift 3
	local current
	current=$(defaults read "${domain}" "${key}" 2>/dev/null | tr -d '[:space:]' || true)
	if [[ ${current} == "${expected}" ]]; then
		already_set "${domain} ${key} = ${expected}"
	else
		defaults write "${domain}" "${key}" "$@"
		updated "${domain} ${key} = ${expected}"
	fi
}

# Finder keeps its view options in nested dicts, which `defaults write` can't edit in place, so
# finder_view_option and finder_view_column edit an exported copy and finder_views_save writes the
# edited top-level dicts back: writing the plist file directly can be clobbered by the copy cached
# in cfprefsd, and importing the whole domain would revert anything Finder saved in the meantime
finder_plist=""
# Space-separated list of the top-level dicts edited in finder_plist
finder_changed_tops=""

function finder_plist_load {
	if [[ -z ${finder_plist} ]]; then
		finder_plist=$(mktemp)
		defaults export com.apple.finder - >"${finder_plist}"
	fi
}

function finder_plist_add {
	# adds an entry to finder_plist if it's missing
	# usage: finder_plist_add <path> <type> [value]
	if ! /usr/libexec/PlistBuddy -c "Print :${1}" "${finder_plist}" >/dev/null 2>&1; then
		/usr/libexec/PlistBuddy -c "Add :${1} ${2}${3:+ ${3}}" "${finder_plist}"
	fi
}

function finder_plist_set {
	# sets a value in finder_plist only if it differs, creating the parent dicts a clean Mac lacks
	# usage: finder_plist_set <label> <dict path> <key> <bool|integer|real|string> <value>
	local label="${1}" path="${2}" key="${3}" type="${4}" value="${5}"
	finder_plist_load
	local current
	current=$(/usr/libexec/PlistBuddy -c "Print :${path}:${key}" "${finder_plist}" 2>/dev/null || true)
	# PlistBuddy prints reals as e.g. 32.000000, and Finder stores some sizes as integers
	if [[ ${type} == "real" && -n ${current} ]]; then
		current=$(printf '%g' "${current}")
	fi
	if [[ ${current} == "${value}" ]]; then
		already_set "${label}"
		return
	fi
	local part parent=""
	local -a parts
	IFS=: read -ra parts <<<"${path}"
	for part in "${parts[@]}"; do
		parent="${parent:+${parent}:}${part}"
		finder_plist_add "${parent}" dict
	done
	/usr/libexec/PlistBuddy -c "Delete :${path}:${key}" "${finder_plist}" >/dev/null 2>&1 || true
	/usr/libexec/PlistBuddy -c "Add :${path}:${key} ${type} ${value}" "${finder_plist}"
	finder_changed_tops="${finder_changed_tops} ${path%%:*}"
	updated "${label}"
}

function finder_view_option {
	# sets a Finder view option, e.g. in the default list view
	# usage: finder_view_option <view settings path> <key> <bool|real|string> <value>
	# example: finder_view_option StandardViewSettings:ListViewSettings iconSize real 32
	finder_plist_set "com.apple.finder ${1}:${2} = ${4}" "$@"
}

function finder_view_column {
	# shows or hides a list view column and puts it at a position (0 is the first column)
	# usage: finder_view_column <list view settings path> <column identifier> <true|false> <position>
	local path="${1}" column="${2}" visible="${3}" position="${4}"
	local label="com.apple.finder ${path} column ${column}"
	if [[ ${path} != *ExtendedListViewSettingsV2 ]]; then
		# ListViewSettings keys its columns by identifier and orders them by index
		finder_plist_set "${label} visible = ${visible}" "${path}:columns:${column}" visible bool \
			"${visible}"
		finder_plist_set "${label} index = ${position}" "${path}:columns:${column}" index integer \
			"${position}"
		return
	fi
	# ExtendedListViewSettingsV2 orders its columns by their place in an array, so find the column
	finder_plist_load
	finder_plist_add "${path%%:*}" dict
	finder_plist_add "${path}" dict
	finder_plist_add "${path}:columns" array
	local i=0 identifier=""
	while true; do
		# Printing past the end of the array fails; `|| true` keeps the error trap quiet
		identifier=$(/usr/libexec/PlistBuddy -c "Print :${path}:columns:${i}:identifier" \
			"${finder_plist}" 2>/dev/null || true)
		[[ -z ${identifier} || ${identifier} == "${column}" ]] && break
		i=$((i + 1))
	done
	# Columns are placed in order, so every position before this one is already taken and the
	# column can't be at an index below it
	if [[ ${identifier} != "${column}" ]]; then
		finder_plist_add "${path}:columns:${position}" dict
		finder_plist_add "${path}:columns:${position}:identifier" string "${column}"
	elif ((i == position)); then
		already_set "${label} position = ${position}"
	else
		# Copying into an array index inserts there, keeping the column's width and sort order
		/usr/libexec/PlistBuddy -c "Copy :${path}:columns:${i} :finder_moved_column" \
			-c "Delete :${path}:columns:${i}" \
			-c "Copy :finder_moved_column :${path}:columns:${position}" \
			-c "Delete :finder_moved_column" "${finder_plist}"
		finder_changed_tops="${finder_changed_tops} ${path%%:*}"
		updated "${label} position = ${position}"
	fi
	finder_plist_set "${label} visible = ${visible}" "${path}:columns:${position}" visible bool \
		"${visible}"
}

function finder_views_save {
	# writes the top-level dicts edited by finder_view_option and finder_view_column back
	local top
	for top in $(echo "${finder_changed_tops}" | tr ' ' '\n' | sort -u); do
		defaults write com.apple.finder "${top}" "$(plutil -extract "${top}" xml1 -o - "${finder_plist}")"
	done
	rm -f "${finder_plist}"
	finder_plist=""
	finder_changed_tops=""
}

function set_pmset {
	# sets a power management setting with sudo only if it differs from the current value
	# usage: set_pmset <-b|-c> <setting> <value>
	local flag="${1}" setting="${2}" value="${3}" section="AC Power:" label="AC"
	if [[ ${flag} == "-b" ]]; then
		section="Battery Power:"
		label="battery"
	fi
	label="pmset ${label} ${setting} = ${value}"
	local current
	current=$(echo "${pmset_custom}" | awk -v section="${section}" -v key="${setting}" \
		'/^[^ ]/ { in_section = ($0 == section) } in_section && $1 == key { print $2 }')
	if [[ ${current} == "${value}" ]]; then
		already_set "${label}"
	elif [[ -z ${current} ]]; then
		# pmset only lists the settings this hardware supports (e.g. no womp on VMs)
		echo -e "⏭️  \033[1;33mSkipping unsupported ${label}.\033[0m"
	else
		sudo pmset "${flag}" "${setting}" "${value}"
		updated "${label}"
	fi
}

function apply_changes {
	# The processes may not be running (e.g. in CI), so never fail on killall
	if [[ " ${changed} " == *" Finder "* ]]; then
		echo -e "\n🔄 \033[1;34mRestarting Finder...\033[0m"
		killall Finder >/dev/null 2>&1 || true
	fi
	if [[ " ${changed} " == *" Dock "* ]]; then
		echo -e "\n🔄 \033[1;34mRestarting Dock...\033[0m"
		killall Dock >/dev/null 2>&1 || true
	fi
	if [[ " ${changed} " == *" menubar "* ]]; then
		echo -e "\n🔄 \033[1;34mRestarting the menu bar...\033[0m"
		killall ControlCenter SystemUIServer >/dev/null 2>&1 || true
	fi
	if [[ " ${changed} " == *" logout "* ]]; then
		echo -e "\nℹ️  \033[1;33mSome of these changes may need a logout to take effect.\033[0m"
	fi
}
# Run on exit rather than at the end: if a later step fails, a rerun would see the settings written
# so far as already set and never restart the apps that need to pick them up
trap apply_changes EXIT

###############################################################################
# macOS preferences                                                           #
###############################################################################

echo -e "\033[1;34m💻 Setting macOS preferences...\033[0m"

# Enable TouchID for sudo
# https://jc0b.computer/posts/enabling-touchid-for-sudo-macos-sonoma/
if [[ ! -f /etc/pam.d/sudo_local ]]; then
	echo -e "🔑 \033[1;35mEnabling TouchID for sudo...\033[0m"
	sudo sh -c 'echo "auth       sufficient     pam_tid.so" >> /etc/pam.d/sudo_local'
	sudo chmod 444 /etc/pam.d/sudo_local
else
	echo -e "✅ \033[1;32mTouchID for sudo is already enabled.\033[0m"
fi

###############################################################################
# Finder                                                                      #
###############################################################################

echo -e "\n📁 \033[1;35mFinder...\033[0m"
on_change="Finder"

set_default NSGlobalDomain AppleShowAllExtensions bool true
set_default NSGlobalDomain NSDocumentSaveNewDocumentsToCloud bool false
set_default com.apple.finder ShowPathbar bool true
set_default com.apple.finder ShowStatusBar bool true
# List view
set_default com.apple.finder FXPreferredViewStyle string Nlsv
# New windows open the home folder
set_default com.apple.finder NewWindowTarget string PfHm
set_default com.apple.finder ShowHardDrivesOnDesktop bool true
set_default com.apple.finder ShowExternalHardDrivesOnDesktop bool true
set_default com.apple.finder ShowMountedServersOnDesktop bool true
set_default com.apple.finder ShowRemovableMediaOnDesktop bool true
set_default com.apple.desktopservices DSDontWriteNetworkStores bool true
set_default com.apple.desktopservices DSDontWriteUSBStores bool true
# Sidebar: show it with Locations expanded and Tags and iCloud collapsed
set_default com.apple.finder ShowSidebar bool true
set_default com.apple.finder SidebarDevicesSectionDisclosedState bool true
set_default com.apple.finder SidebarPlacesSectionDisclosedState bool true
# Apple's own typo: the key really is "Sction"
set_default com.apple.finder SidebarTagsSctionDisclosedState bool false
set_default com.apple.finder SidebariCloudDriveSectionDisclosedState bool false

# The list view every location uses: the default for Finder windows (StandardViewSettings) and
# open/save panels (FK_StandardViewSettings), plus the locations Finder keeps their own view for.
# The Trash is sorted by date added, and finder_views.py makes Downloads match it
for settings in StandardViewSettings FK_StandardViewSettings ComputerViewSettings ICloudViewSettings \
	NetworkViewSettings TrashViewSettings; do
	sort=name
	[[ ${settings} == TrashViewSettings ]] && sort=dateAdded
	# ExtendedListViewSettingsV2 supersedes ListViewSettings on newer macOS
	for view in "${settings}:ListViewSettings" "${settings}:ExtendedListViewSettingsV2"; do
		finder_view_option "${view}" calculateAllSizes bool true
		# 32 is the "large" icon size option
		finder_view_option "${view}" iconSize real 32
		finder_view_option "${view}" textSize real 13
		finder_view_option "${view}" sortColumn string "${sort}"
		finder_view_option "${view}" useRelativeDates bool true
		finder_view_option "${view}" showIconPreview bool true
		# Set every column, in order, so a clean Mac, which has no column list yet, gets exactly these
		shown=(name dateModified dateCreated size kind)
		hidden=(label version comments dateLastOpened ubiquity shareOwner shareLastEditor
			invitationStatus)
		if [[ ${sort} == dateAdded ]]; then
			shown=(name dateAdded "${shown[@]:1}")
		else
			hidden+=(dateAdded)
		fi
		position=0
		for column in "${shown[@]}"; do
			finder_view_column "${view}" "${column}" true "${position}"
			position=$((position + 1))
		done
		for column in "${hidden[@]}"; do
			finder_view_column "${view}" "${column}" false "${position}"
			position=$((position + 1))
		done
	done
done

# Desktop icons: sorted by name, with item info such as the free space under each drive
finder_view_option DesktopViewSettings:IconViewSettings arrangeBy string name
finder_view_option DesktopViewSettings:IconViewSettings iconSize real 64
finder_view_option DesktopViewSettings:IconViewSettings showItemInfo bool true
finder_views_save

# The home folder and the folders in it keep any view saved for them over the defaults above
uv run "${root}/scripts/finder_views.py"

###############################################################################
# Trackpad                                                                    #
###############################################################################

echo -e "\n👆 \033[1;35mTrackpad...\033[0m"
on_change="logout"

# Gestures are stored per driver (built-in and Bluetooth trackpads), and mirrored in the
# -currentHost global domain
for domain in com.apple.AppleMultitouchTrackpad com.apple.driver.AppleBluetoothMultitouch.trackpad; do
	# Tap to click
	set_default "${domain}" Clicking bool true
	# Swipe between pages with three fingers
	set_default "${domain}" TrackpadThreeFingerHorizSwipeGesture int 1
	# Swipe between full-screen apps with four fingers
	set_default "${domain}" TrackpadFourFingerHorizSwipeGesture int 2
	# Mission Control with three or four fingers swiping up
	set_default "${domain}" TrackpadThreeFingerVertSwipeGesture int 2
	set_default "${domain}" TrackpadFourFingerVertSwipeGesture int 2
done
set_default NSGlobalDomain com.apple.mouse.tapBehavior int 1
set_default -currentHost NSGlobalDomain com.apple.mouse.tapBehavior int 1
set_default -currentHost NSGlobalDomain com.apple.trackpad.threeFingerHorizSwipeGesture int 1
set_default -currentHost NSGlobalDomain com.apple.trackpad.fourFingerHorizSwipeGesture int 2
set_default -currentHost NSGlobalDomain com.apple.trackpad.threeFingerVertSwipeGesture int 2
set_default -currentHost NSGlobalDomain com.apple.trackpad.fourFingerVertSwipeGesture int 2
set_default NSGlobalDomain com.apple.trackpad.scaling float 2.5
# Swipe between pages with two fingers
set_default NSGlobalDomain AppleEnableSwipeNavigateWithScrolls bool true

###############################################################################
# Language & region                                                           #
###############################################################################

echo -e "\n🌍 \033[1;35mLanguage & region...\033[0m"
on_change="logout"

set_collection NSGlobalDomain AppleLanguages '("en-US")' -array en-US
set_default NSGlobalDomain AppleLocale string en_US
set_default NSGlobalDomain AppleMetricUnits bool true
set_default NSGlobalDomain AppleMeasurementUnits string Centimeters
set_default NSGlobalDomain AppleTemperatureUnit string Celsius
set_default NSGlobalDomain AppleICUForce24HourTime bool true
# Short date format (key 1); the other keys hold the medium/long/full formats, so leave them alone
label="NSGlobalDomain AppleICUDateFormatStrings 1 = y-MM-dd"
if [[ $(defaults export NSGlobalDomain - | plutil -extract AppleICUDateFormatStrings.1 raw -o - - 2>/dev/null || true) == "y-MM-dd" ]]; then
	already_set "${label}"
else
	defaults write NSGlobalDomain AppleICUDateFormatStrings -dict-add 1 y-MM-dd
	updated "${label}"
fi

###############################################################################
# Keyboard & text                                                             #
###############################################################################

echo -e "\n⌨️  \033[1;35mKeyboard & text...\033[0m"
on_change="logout"

set_default NSGlobalDomain KeyRepeat int 2
set_default NSGlobalDomain InitialKeyRepeat int 25
set_default NSGlobalDomain ApplePressAndHoldEnabled bool false
# Full keyboard navigation (Tab moves focus between all controls)
set_default NSGlobalDomain AppleKeyboardUIMode int 3
# Fn/Globe key shows emoji & symbols
set_default com.apple.HIToolbox AppleFnUsageType int 2
set_default NSGlobalDomain NSAutomaticSpellingCorrectionEnabled bool false
set_default NSGlobalDomain NSAutomaticCapitalizationEnabled bool false
set_default NSGlobalDomain NSAutomaticDashSubstitutionEnabled bool false
set_default NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled bool false
set_default NSGlobalDomain NSAutomaticPeriodSubstitutionEnabled bool false

###############################################################################
# Appearance & windows                                                        #
###############################################################################

echo -e "\n🌙 \033[1;35mAppearance & windows...\033[0m"
on_change="logout"

set_default NSGlobalDomain AppleInterfaceStyle string Dark
# Reopen windows when relaunching apps ("Close windows when quitting an application" off)
set_default NSGlobalDomain NSQuitAlwaysKeepsWindows bool true
set_default com.apple.WindowManager EnableTiledWindowMargins bool false
# Hide widgets on the desktop and in Stage Manager
set_default com.apple.WindowManager StandardHideWidgets bool true
set_default com.apple.WindowManager StageManagerHideWidgets bool true

###############################################################################
# Dock, Mission Control & hot corners                                         #
###############################################################################

echo -e "\n🚢 \033[1;35mDock, Mission Control & hot corners...\033[0m"
on_change="Dock"

set_default com.apple.dock autohide bool true
set_default com.apple.dock show-recents bool false
set_default com.apple.dock tilesize int 64
# Don't rearrange Spaces based on most recent use
set_default com.apple.dock mru-spaces bool false
# Hot corners: 1 = no action, 2 = Mission Control, 5 = start screen saver, 6 = disable screen saver
set_default com.apple.dock wvous-tl-corner int 5
set_default com.apple.dock wvous-tr-corner int 2
set_default com.apple.dock wvous-bl-corner int 6
set_default com.apple.dock wvous-br-corner int 1
for corner in tl tr bl br; do
	set_default com.apple.dock "wvous-${corner}-modifier" int 0
done

###############################################################################
# Menu bar                                                                    #
###############################################################################

echo -e "\n📊 \033[1;35mMenu bar...\033[0m"
on_change="menubar"

# Never auto-hide the menu bar
set_default com.apple.controlcenter AutoHideMenuBarOption int 3
set_default NSGlobalDomain AppleMenuBarVisibleInFullscreen bool true
set_default -currentHost com.apple.Spotlight MenuItemHidden bool true
set_default com.apple.Siri StatusMenuVisible bool false
set_default -currentHost com.apple.controlcenter BatteryShowPercentage bool true

###############################################################################
# Screenshots                                                                 #
###############################################################################

echo -e "\n📸 \033[1;35mScreenshots...\033[0m"
on_change=""

set_default com.apple.screencapture location string "${HOME}/Downloads"
set_default com.apple.screencapture show-thumbnail bool false

###############################################################################
# Lock screen                                                                 #
###############################################################################

echo -e "\n🔒 \033[1;35mLock screen...\033[0m"
on_change=""

# Start the screen saver after 5 minutes
set_default -currentHost com.apple.screensaver idleTime int 300

# Require password 5 seconds after sleep or screen saver begins
label="screen lock delay = 5 seconds"
if [[ $(sysadminctl -screenLock status 2>&1 || true) == *"screenLock delay is 5 seconds"* ]]; then
	already_set "${label}"
elif [[ ${CI-} == "true" ]]; then
	echo -e "⏭️  \033[1;33mSkipping ${label} in CI.\033[0m"
# A profile's screensaver settings land here (machine- or user-level), and macOS then refuses to
# change the delay, so don't ask for a password that can't help.
elif [[ -f "/Library/Managed Preferences/com.apple.screensaver.plist" ||
	-f "/Library/Managed Preferences/${USER}/com.apple.screensaver.plist" ]]; then
	echo -e "ℹ️  \033[1;34mSkipping ${label}: the screen lock is managed by a configuration profile.\033[0m"
else
	echo -e "🔑 \033[1;35mSetting the screen lock delay requires your login password:\033[0m"
	# Not worth aborting the rest of the setup over, e.g. on a mistyped password.
	if sysadminctl -screenLock 5 -password -; then
		updated "${label}"
	else
		echo -e "⏭️  \033[1;33mCouldn't set the ${label}, set it in System Settings > Lock Screen.\033[0m"
	fi
fi

###############################################################################
# Energy                                                                      #
###############################################################################

echo -e "\n🔋 \033[1;35mEnergy...\033[0m"
on_change=""

pmset_custom=$(pmset -g custom)

# Desktop Macs and CI VMs have no battery
if [[ ${pmset_custom} == *"Battery Power:"* ]]; then
	set_pmset -b displaysleep 5
	set_pmset -b womp 0
else
	echo -e "⏭️  \033[1;33mNo battery found, skipping battery settings.\033[0m"
fi
set_pmset -c displaysleep 20
set_pmset -c sleep 0
set_pmset -c womp 1

###############################################################################
# Firewall                                                                    #
###############################################################################

echo -e "\n🧱 \033[1;35mFirewall...\033[0m"
on_change=""

socketfilterfw="/usr/libexec/ApplicationFirewall/socketfilterfw"
if [[ $(${socketfilterfw} --getglobalstate) == *"enabled"* ]]; then
	already_set "firewall enabled"
else
	sudo "${socketfilterfw}" --setglobalstate on >/dev/null
	updated "firewall enabled"
fi
