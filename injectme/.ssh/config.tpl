Host *
	IdentityAgent "~/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"

Host {{ op://5ebyeb4rgmu73mcoodmzro4kyu/sbpc6n3eorvjrlpyzhioxuture/name }}
	HostName {{ op://5ebyeb4rgmu73mcoodmzro4kyu/sbpc6n3eorvjrlpyzhioxuture/URL }}
	User {{ op://5ebyeb4rgmu73mcoodmzro4kyu/sbpc6n3eorvjrlpyzhioxuture/username }}

Host {{ op://5ebyeb4rgmu73mcoodmzro4kyu/2zumvkvybp4oqesi7ls7g3ptqq/name }}
	HostName {{ op://5ebyeb4rgmu73mcoodmzro4kyu/2zumvkvybp4oqesi7ls7g3ptqq/URL }}
	User {{ op://5ebyeb4rgmu73mcoodmzro4kyu/2zumvkvybp4oqesi7ls7g3ptqq/username }}
	Port {{ op://5ebyeb4rgmu73mcoodmzro4kyu/2zumvkvybp4oqesi7ls7g3ptqq/port }}
	ProxyCommand {{ op://5ebyeb4rgmu73mcoodmzro4kyu/2zumvkvybp4oqesi7ls7g3ptqq/command }}

Host {{ op://5ebyeb4rgmu73mcoodmzro4kyu/exely6m4mmyhfy5chd7se7ph5a/name }}
	HostName {{ op://5ebyeb4rgmu73mcoodmzro4kyu/exely6m4mmyhfy5chd7se7ph5a/URL }}
	User {{ op://5ebyeb4rgmu73mcoodmzro4kyu/exely6m4mmyhfy5chd7se7ph5a/username }}
	Port {{ op://5ebyeb4rgmu73mcoodmzro4kyu/exely6m4mmyhfy5chd7se7ph5a/port }}

# Tailnet hosts go through `ts` (userspace tailscaled, see .functions) while it runs. `final`
# makes this see the HostName a Host block resolved to; the exec fails when ts is stopped.
Match final exec "tailscale --socket=$HOME/.local/state/ts/tailscaled.sock ip -1 %h >/dev/null 2>&1"
	ProxyCommand tailscale --socket=$HOME/.local/state/ts/tailscaled.sock nc %h %p
