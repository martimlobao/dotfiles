if [[ ${CI:-"false"} == "true" ]]; then
	# Exit on error for CI
	set -e
fi

# Homebrew on macOS or Linux
if [[ "$(uname)" == "Darwin" ]]; then
	eval "$(/opt/homebrew/bin/brew shellenv)"
else
	eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
fi

# Add uv to PATH
export PATH="$HOME/.local/bin:$PATH"
