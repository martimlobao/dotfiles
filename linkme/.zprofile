if [[ ${CI:-"false"} == "true" ]]; then
	# Exit on error for CI
	set -e
fi

# Homebrew on macOS or Linux
if [[ "$(uname)" == "Darwin" ]]; then
	if [[ -f /opt/homebrew/bin/brew ]]; then
		eval "$(/opt/homebrew/bin/brew shellenv)"
	else
		# for old versions of macOS
		eval "$(/usr/local/bin/brew shellenv)"
	fi
else
	eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
fi

# Add uv to PATH
export PATH="$HOME/.local/bin:$PATH"

# Add cargo to PATH
export PATH="$HOME/.cargo/bin:$PATH"

# Add scripts to PATH
export PATH="$HOME/.dotfiles/scripts:$PATH"
