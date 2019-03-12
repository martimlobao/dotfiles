#!/usr/bin/env bash

# Ask to set display resolution and density.
echo "Please select your preferred display resolution."
# Can't run automatically without user manually granting permission:
# osascript -e 'tell application "System Preferences"' -e 'set the current pane to pane id "com.apple.preference.displays"' -e 'tell application "System Events"' -e 'tell window 1 of application process "System Preferences"' -e 'click radio button "Display" of tab group 1' -e 'click radio button "Scaled" of radio group 1 of tab group 1' -e 'click radio button 4 of radio group 1 of group 2 of tab group 1' -e 'end tell' -e 'end tell' -e 'end tell' -e 'quit application "System Preferences"'
osascript -e 'tell app "System Preferences"' -e 'activate' -e 'set the current pane to pane id "com.apple.preference.displays"' -e 'end tell'
