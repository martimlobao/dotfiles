# Coding agents can't answer 1Password prompts, so they get their own git config.
if [[ -n ${CLAUDECODE-}${CODEX_THREAD_ID-} ]]; then
	export GIT_CONFIG_GLOBAL=$HOME/.gitconfig.agent GIT_TERMINAL_PROMPT=0
fi
