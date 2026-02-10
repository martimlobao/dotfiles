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
	uuid=$(system_profiler SPHardwareDataType | awk '/Hardware UUID/ {print $3}')
	serial=$(system_profiler SPHardwareDataType | awk '/Serial Number/ {print $4}')
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
if ! command -v brew &>/dev/null; then
	/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
	echo -e "🍻 \033[1;32mHomebrew installed.\033[0m"
else
	echo -e "🍻 \033[1;32mHomebrew is already installed.\033[0m"
fi

###############################################################################
# Install dotfiles                                                            #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning dotsync.sh...\033[0m"
sleep 1
./scripts/dotsync.sh "${1-}"

###############################################################################
# macOS preferences                                                           #
###############################################################################
if [[ ${os} == "Darwin" ]]; then
	sleep 1
	echo
	echo -e "🚀 \033[1;33mRunning macos.sh...\033[0m"
	./scripts/macos.sh "${1-}"
fi

###############################################################################
# CI exit                                                                     #
###############################################################################
if [[ ${CI-} == "true" ]]; then
	echo
	echo -e "⛔️ \033[1;33mWarning: macOS is not supported in CI after this point.\033[0m"
	exit 0
fi

###############################################################################
# Install apps and software                                                   #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning install.sh...\033[0m"
sleep 1
if [[ ${os} == "Darwin" ]]; then
	./scripts/install.sh ${1+"$1"}
elif [[ ${os} == "Linux" ]]; then
	./scripts/install.sh --no-mas --no-cask ${1+"$1"}
fi

###############################################################################
# Linux exit                                                                  #
###############################################################################
if [[ ${os} == "Linux" ]]; then
	echo
	echo -e "⛔️ \033[1;33mWarning: Linux is not supported after this point.\033[0m"
	exit 0
fi

###############################################################################
# Configure macOS Dock                                                        #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning dock.sh...\033[0m"
sleep 1
./scripts/dock.sh

###############################################################################
# Install Aerial Live Wallpapers                                              #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning aerials.py...\033[0m"
sleep 1
./scripts/aerials.py -d -y

###############################################################################
# Install Cursor extensions                                                   #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning code.sh...\033[0m"
sleep 1
./scripts/code.sh --sync "${1-}"

###############################################################################
# Local settings and variables                                                #
###############################################################################
echo
echo -e "🚀 \033[1;33mRunning local.sh...\033[0m"
sleep 1
./scripts/local.sh "${1-}"

echo
echo -e "🎉 \033[1;32mSetup complete!\033[0m"
