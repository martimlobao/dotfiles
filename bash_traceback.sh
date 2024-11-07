#!/usr/bin/env bash

# Bash traceback (from https://gist.github.com/Asher256/4c68119705ffa11adb7446f297a7beae)
set -o errexit # stop the script each time a command fails
set -o nounset # stop if you attempt to use an undef variable

function bash_traceback() {
	local lasterr="$?"
	set +o xtrace
	local code="-1"
	local bash_command=${BASH_COMMAND}
	echo "Error in ${BASH_SOURCE[1]}:${BASH_LINENO[0]} ('${bash_command}' exited with status ${lasterr})" >&2
	if [[ ${#FUNCNAME[@]} -gt 2 ]]; then
		# Print out the stack trace described by $function_stack
		echo "Traceback of ${BASH_SOURCE[1]} (most recent call last):" >&2
		for ((i = 0; i < ${#FUNCNAME[@]} - 1; i++)); do
			local funcname="${FUNCNAME[${i}]}"
			[[ ${i} -eq "0" ]] && funcname=${bash_command}
			echo -e "  ${BASH_SOURCE[i + 1]}:${BASH_LINENO[${i}]}\\t${funcname}" >&2
		done
	fi
	echo "Exiting with status ${code}" >&2
	exit "${code}"
}

# provide an error handler whenever a command exits nonzero
trap 'bash_traceback' ERR

# propagate ERR trap handler functions, expansions and subshells
set -o errtrace
