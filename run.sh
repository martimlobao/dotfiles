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
echo -e "\033[1;33m💻 OS detected:\033[0m   ${os}"

archname="$(arch)"
echo -e "\033[1;33m💻 Arch detected:\033[0m ${archname}"

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
echo -e "\033[1;33m💻 Hardware UUID:\033[0m ${uuid}"
echo -e "\033[1;33m💻 Serial Number:\033[0m ${serial:-N/A}"
echo -e "\033[1;33m💻 Model:\033[0m         ${model:-N/A}"

###############################################################################
# Install Homebrew                                                            #
###############################################################################
echo
echo -e "\033[1;33m🍺 Installing Homebrew...\033[0m"
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
echo -e "\033[1;33m🚀 Running dotsync.sh...\033[0m"
sleep 1
./dotsync.sh "${1-}"

###############################################################################
# Linux exit                                                                  #
###############################################################################
if [[ ${os} == "Linux" ]]; then
	echo
	echo -e "\033[1;33m ⛔️ Warning: Linux is not supported after this point.\033[0m"
	exit 0
fi

###############################################################################
# macOS preferences                                                           #
###############################################################################
sleep 1
echo
echo -e "\033[1;33m🚀 Running macos.sh...\033[0m"
./macos.sh "${1-}"

###############################################################################
# CI exit                                                                     #
###############################################################################
if [[ ${CI-} == "true" ]]; then
	echo
	echo -e "\033[1;33m ⛔️ Warning: macOS is not supported in CI after this point.\033[0m"
	exit 0
fi

###############################################################################
# Install apps and software                                                   #
###############################################################################
echo
echo -e "\033[1;33m🚀 Running install.sh...\033[0m"
sleep 1
./install.sh "${1-}"
echo
echo -e "\033[1;33m🚀 Running dock.sh...\033[0m"
sleep 1
./dock.sh

###############################################################################
# Local settings and variables                                                #
###############################################################################
echo
echo -e "\033[1;33m🚀 Running local.sh...\033[0m"
sleep 1
./local.sh "${1-}"

echo
echo -e "\033[1;32m🎉 Setup complete!\033[0m"
