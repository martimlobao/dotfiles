* change screenshot location

* snap icons to grid in desktop

* show storage used in HD on desktop

* default browser
brew install defaultbrowser
defaultbrowser browser

* show sound in menu bar

* display resolution
echo "Select screen resolution and close System Settings when done"
open -W x-apple.systempreferences:com.apple.Displays-Settings.extension

* trackpad tracking speed
# Increase tracking speed for trackpad
defaults write -g com.apple.trackpad.scaling 2.5

* tap to click
# Trackpad: enable tap to click for this user and for the login screen
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -int 1
defaults write com.apple.AppleMultitouchTrackpad Clicking -int 1
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1

* right click with 2 fingers
defaults write com.apple.AppleMultitouchTrackpad TrackpadCornerSecondaryClick -int 0
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadCornerSecondaryClick -int 0
defaults write com.apple.AppleMultitouchTrackpad TrackpadRightClick -int 1
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadRightClick -int 1

* swipe between full-screen apps with 4 fingers
defaults write com.apple.AppleMultitouchTrackpad TrackpadFourFingerHorizSwipeGesture -int 2
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadFourFingerHorizSwipeGesture -int 2

# swipe between pages with 2 or 3 fingers
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerHorizSwipeGesture -int 1
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerHorizSwipeGesture -int 1
defaults write NSGlobalDomain AppleEnableSwipeNavigateWithScrolls -int 1

# KEYBOARD
# key repeat rate and delay until repeat
defaults write NSGlobalDomain InitialKeyRepeat -int 15
defaults write NSGlobalDomain KeyRepeat -int 2

* screen saver activate
* turn off display
* require password after screen saver
* set screen saver
echo "Select screensaver and close System Settings when done"
open -W x-apple.systempreferences:com.apple.ScreenSaver-Settings.extension
# todo: if you want to automate this more, see: https://forum.iscreensaver.com/t/understanding-the-macos-sonoma-screensaver-plist/718/4
# convert plist from binary to regular: https://osxdaily.com/2016/03/10/convert-plist-file-xml-binary-mac-os-x-plutil/
* set wallpaper
* desktop and dock

* automatically hide dock
# Automatically hide and show the Dock
defaults write com.apple.dock autohide -bool true

# don't show recents
# defaults write com.apple.dock show-recents -bool false

# System Events got an error: Script Editor is not allowed assistive access.

* set dock zoom
* control center: bluetooth show in menu bar / keyboard brightness show in control center
* do not order spaced by most recent: automatically arrange spaces based on most recent use
# Don’t automatically rearrange Spaces based on most recent use
defaults write com.apple.dock mru-spaces -bool false
* set clock to 24 hours
* set metric units
* set date format

* keyboard navigation
# Enable full keyboard access for all controls (e.g. enable Tab in modal dialogs)
defaults write NSGlobalDomain AppleKeyboardUIMode -int 3

##########
# FINDER #
##########
# Show all filename extensions:
defaults write NSGlobalDomain AppleShowAllExtensions -bool true
defaults write -g AppleShowAllExtensions -bool true

# Finder: show status bar
defaults write com.apple.finder ShowStatusBar -bool true
# Finder: show path bar
defaults write com.apple.finder ShowPathbar -bool true

# Show macOS system ~/Library hidden by default:
chflags hidden ~/Library

# Show hard drives and network drives on the Desktop
defaults write com.apple.finder ShowHardDrivesOnDesktop -bool true
defaults write com.apple.finder ShowMountedServersOnDesktop -bool true

# New Finder windows points to home
defaults delete com.apple.finder NewWindowTargetPath
defaults write com.apple.finder NewWindowTarget -string "PfHm"

# Enable full keyboard access for all controls (e.g. enable Tab in modal dialogs)
defaults write NSGlobalDomain AppleKeyboardUIMode -int 3

# Tracking speed: maximum 5.0
defaults write -g com.apple.trackpad.scaling 2.5

# Trackpad: enable tap to click for this user and for the login screen
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
defaults write NSGlobalDomain com.apple.mouse.tapBehavior -int 1

# Disable auto-correct
defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false
# Disable automatic capitalization
defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false
# Disable smart dashes
defaults write NSGlobalDomain NSAutomaticDashSubstitutionEnabled -bool false
# Disable automatic period
defaults write NSGlobalDomain NSAutomaticPeriodSubstitutionEnabled -bool false
# Disable smart quotes
defaults write NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false

# Calculate all sizes
/usr/libexec/PlistBuddy -c "Set :'FK_StandardViewSettings':'ExtendedListViewSettingsV2':'calculateAllSizes' 'true'" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :'FK_StandardViewSettings':'ListViewSettings':'calculateAllSizes' 'true'" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :'FK_DefaultListViewSettings':'calculateAllSizes' 'true'" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :'StandardViewSettings':'ExtendedListViewSettingsV2':'calculateAllSizes' 'true'" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :'StandardViewSettings':'ListViewSettings':'calculateAllSizes' 'true'" ~/Library/Preferences/com.apple.finder.plist

# Default list view icon size
/usr/libexec/PlistBuddy -c "Set :'FK_StandardViewSettings':'ExtendedListViewSettingsV2':'iconSize' '32'" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :'FK_StandardViewSettings':'ListViewSettings':'iconSize' '32'" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :'FK_DefaultListViewSettings':'iconSize' '16'" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :'StandardViewSettings':'ExtendedListViewSettingsV2':'iconSize' '32'" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :'StandardViewSettings':'ListViewSettings':'iconSize' '32'" ~/Library/Preferences/com.apple.finder.plist

####

# Use metric units and 24 hour time
defaults write NSGlobalDomain AppleICUForce24HourTime -bool true
defaults write NSGlobalDomain AppleMeasurementUnits -string "Centimeters"
defaults write NSGlobalDomain AppleMetricUnits -bool true
defaults write NSGlobalDomain AppleTemperatureUnit -string "Celsius"

# Save to disk by default, instead of iCloud
defaults write NSGlobalDomain NSDocumentSaveNewDocumentsToCloud -bool false

# Require password immediately after sleep or screen saver begins
defaults write com.apple.screensaver askForPassword -int 1
defaults write com.apple.screensaver askForPasswordDelay -int 0

defaults read com.apple.finder

# https://medium.com/@laclementine/dotfile-for-mac-efe082ad0d6a
# Get current Username and User ID
CURRENT_USER=$(stat -f %Su /dev/console)
USER_ID=$(id -u "$CURRENT_USER")

# Show all filename extensions
sudo -u "$CURRENT_USER" defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Show path bar
# sudo -u "$CURRENT_USER" defaults write com.apple.finder ShowPathbar -bool true

# Show status bar
# sudo -u "$CURRENT_USER" defaults write com.apple.finder ShowStatusBar -bool true

# New Finder windows points to home
# sudo -u "$CURRENT_USER" defaults write com.apple.finder NewWindowTarget -string "PfHm"

# Expand print panel by default
sudo -u "$CURRENT_USER" defaults write NSGlobalDomain PMPrintingExpandedStateForPrint -bool true
sudo -u "$CURRENT_USER" defaults write NSGlobalDomain PMPrintingExpandedStateForPrint2 -bool true

# Avoid creating .DS_Store files on network or USB volumes
sudo -u "$CURRENT_USER" defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true
sudo -u "$CURRENT_USER" defaults write com.apple.desktopservices DSDontWriteUSBStores -bool true

# Disable recent apps in the Dock
# launchctl asuser "$USER_ID" sudo -u "$CURRENT_USER" defaults write com.apple.dock show-recents -int 0

# Display all files and folders sizes
sudo -u "$CURRENT_USER" /usr/libexec/PlistBuddy -c "Set :'FK_StandardViewSettings':'ExtendedListViewSettingsV2':'calculateAllSizes' 'true'" /Users/$CURRENT_USER/Library/Preferences/com.apple.finder.plist
sudo -u "$CURRENT_USER" /usr/libexec/PlistBuddy -c "Set :'FK_StandardViewSettings':'ListViewSettings':'calculateAllSizes' 'true'" /Users/$CURRENT_USER/Library/Preferences/com.apple.finder.plist
sudo -u "$CURRENT_USER" /usr/libexec/PlistBuddy -c "Set :'StandardViewSettings':'ExtendedListViewSettingsV2':'calculateAllSizes' 'true'" /Users/$CURRENT_USER/Library/Preferences/com.apple.finder.plist
sudo -u "$CURRENT_USER" /usr/libexec/PlistBuddy -c "Set :'StandardViewSettings':'ListViewSettings':'calculateAllSizes' 'true'" /Users/$CURRENT_USER/Library/Preferences/com.apple.finder.plist

# Show hard drives and network drives on the Desktop
# sudo -u "$CURRENT_USER" defaults write com.apple.finder ShowHardDrivesOnDesktop -bool true
# sudo -u "$CURRENT_USER" defaults write com.apple.finder ShowMountedServersOnDesktop -bool true

# https://github.com/br3ndonland/dotfiles/blob/main/scripts/macos.sh

tell application "System Settings"
set the current pane to pane id "com.apple.Displays-Settings.extension"
end tell
