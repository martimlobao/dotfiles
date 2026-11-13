#!/usr/bin/env bash

# Root is $DOTPATH if it exists, otherwise the directory of this script
root=$(realpath "${DOTPATH:-$(dirname "$(realpath "$0")")}")

# Source the bash_traceback.sh file
source "${root}/bash_traceback.sh"

###############################################################################
# OS and architecture detection                                               #
###############################################################################
os="$(uname)"
if [[ ${os} != 'Darwin' ]] && [[ ${os} != 'Linux' ]]; then
	echo -e "❌ \033[1;31mError: Unsupported OS: ${os}\033[0m"
	exit 1
fi
echo -e "💻 \033[1;33mOS detected:\033[0m   ${os}"

archname="$(arch)"
echo -e "💻 \033[1;33mArch detected:\033[0m ${archname}"

# Get hardware identifier
if [[ ${os} == "Darwin" ]]; then
	uuid=$(system_profiler SPHardwareDataType 2>/dev/null | awk '/Hardware UUID/ {print $3}')
	serial=$(system_profiler SPHardwareDataType 2>/dev/null | awk '/Serial Number/ {print $4}')
	model=$(sysctl hw.model | sed 's/hw.model: //')
else
	uuid=$(cat /sys/class/dmi/id/product_uuid 2>/dev/null ||
		cat /etc/machine-id 2>/dev/null ||
		cat /var/lib/dbus/machine-id 2>/dev/null || echo '')
	serial=$(cat /sys/class/dmi/id/serial_number 2>/dev/null ||
		cat /sys/devices/virtual/dmi/id/product_serial 2>/dev/null ||
		cat /sys/devices/virtual/dmi/id/product_uuid 2>/dev/null || echo '')
	model=$(cat /sys/devices/virtual/dmi/id/product_name 2>/dev/null ||
		cat /sys/devices/virtual/dmi/id/product_version 2>/dev/null || echo '')
fi
echo -e "💻 \033[1;33mHardware UUID:\033[0m ${uuid}"
echo -e "💻 \033[1;33mSerial Number:\033[0m ${serial:-N/A}"
echo -e "💻 \033[1;33mModel:\033[0m         ${model:-N/A}"

###############################################################################
# Install Homebrew                                                            #
###############################################################################
echo
echo -e "🍺 \033[1;33mInstalling Homebrew...\033[0m"
# A fresh shell doesn't have brew on PATH yet (even right after installing it), so look for it at
# its known install locations and load its environment into this session. A brew whose shellenv
# fails counts as not installed.
load_brew() {
	local brew env
	for brew in "$(command -v brew || true)" /opt/homebrew/bin/brew /usr/local/bin/brew \
		/home/linuxbrew/.linuxbrew/bin/brew; do
		if [[ -x ${brew} ]]; then
			env=$("${brew}" shellenv) || return 1
			eval "${env}"
			return 0
		fi
	done
	return 1
}
if load_brew; then
	echo -e "🍻 \033[1;32mHomebrew is already installed.\033[0m"
else
	/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
	load_brew
	echo -e "🍻 \033[1;32mHomebrew installed.\033[0m"
fi

###############################################################################
# Install uv                                                                  #
###############################################################################
echo
echo -e "🥚 \033[1;33mInstalling uv...\033[0m"
sleep 1
if ! command -v uv &>/dev/null; then
	brew install uv
	echo -e "🐍 \033[1;32muv installed.\033[0m"
else
	echo -e "🐍 \033[1;32muv is already installed.\033[0m"
fi

###############################################################################
# Install dotfiles                                                            #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning dotsync.sh...\033[0m"
sleep 1
"${root}/scripts/dotsync.sh" "${1-}"

###############################################################################
# macOS preferences                                                           #
###############################################################################
if [[ ${os} == "Darwin" ]]; then
	sleep 1
	echo
	echo -e "🚀 \033[1;33mRunning macos.sh...\033[0m"
	"${root}/scripts/macos.sh" "${1-}"
fi

###############################################################################
# CI exit                                                                     #
###############################################################################
if [[ ${CI-} == "true" ]]; then
	echo
	echo -e "⛔️ \033[1;33mWarning: CI is not supported after this point.\033[0m"
	exit 0
fi

###############################################################################
# Install apps and software                                                   #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning app sync...\033[0m"
sleep 1
if [[ ${os} == "Darwin" ]]; then
	"${root}/scripts/app.py" sync ${1+"$1"}
elif [[ ${os} == "Linux" ]]; then
	"${root}/scripts/app.py" sync --no-mas --no-cask ${1+"$1"}
fi

###############################################################################
# Change shell to zsh                                                         #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning chshell.sh...\033[0m"
sleep 1
"${root}/scripts/chshell.sh" "${1-}"

###############################################################################
# Linux exit                                                                  #
###############################################################################
if [[ ${os} == "Linux" ]]; then
	echo
	echo -e "✅ \033[1;32mLinux setup complete (skipping macOS-only steps).\033[0m"
	exit 0
fi

###############################################################################
# Set default browser                                                         #
###############################################################################
# Runs after app sync, which installs Dia and defaultbrowser
echo
browsers=$(defaultbrowser 2>/dev/null || true)
if [[ ${browsers} == *"* dia"* ]]; then
	echo -e "✅ \033[1;32mDia is already the default browser.\033[0m"
# App sync can skip casks or formulae, leaving Dia or defaultbrowser uninstalled
elif [[ ${browsers} != *" dia"* ]]; then
	echo -e "⏭️  \033[1;33mSkipping the default browser: Dia or defaultbrowser isn't installed.\033[0m"
else
	echo -e "🌐 \033[1;33mSetting Dia as the default browser, confirm it in the dialog...\033[0m"
	defaultbrowser dia
fi

###############################################################################
# Configure macOS Dock                                                        #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning dock.sh...\033[0m"
sleep 1
"${root}/scripts/dock.sh"

###############################################################################
# Install Aerial Live Wallpapers                                              #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning aerials.py...\033[0m"
sleep 1
"${root}/scripts/aerials.py" -d -y

###############################################################################
# Local settings and variables                                                #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning local.sh...\033[0m"
sleep 1
"${root}/scripts/local.sh" "${1-}"

echo
echo -e "🎉 \033[1;32mSetup complete!\033[0m"
