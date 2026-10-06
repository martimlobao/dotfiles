tell application "System Settings"
	activate
	reveal pane id "com.apple.Displays-Settings.extension"
	delay 1
	set CurrentPane to the id of the current pane
	set the clipboard to CurrentPane
	anchors of current pane
	get the name of every anchor of current pane
	tell current pane to reveal anchor "resolutionSection"
	get the name of every anchor of current anchor
end tell


{"advancedSection", "ambienceSection", "arrangementSection", "characteristicSection", "displaysSection", "miscellaneousSection",
"nightShiftSection", "profileSection", "resolutionSection", "sidecarSection"}

tell application "System Settings"
	reveal anchor "resolutionSection" of pane id "com.apple.Displays-Settings.extension"
end tell
open x-apple.systempreferences:com.apple.Displays-Settings.extension
