# Homebrew
eval "$(/opt/homebrew/bin/brew shellenv)"

# Shell completion for rye
if [ ! -f "$ZSH/plugins/rye/_rye" ] && command -v rye >/dev/null; then
	mkdir -p "$ZSH/plugins/rye"
	rye self completion -s zsh > "$ZSH/plugins/rye/_rye"
fi

# Add rye to PATH
source "$HOME/.rye/env"
