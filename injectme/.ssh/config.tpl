Host *
	IdentityAgent "~/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"

Host {{ op://Private/SSH Hosts/lem }}
	SetEnv TERM=xterm-256color

Host {{ op://Private/SSH Hosts/lem-tailscale }}
	SetEnv TERM=xterm-256color

Host lem
	SetEnv TERM=xterm-256color

Host {{ op://5ebyeb4rgmu73mcoodmzro4kyu/sbpc6n3eorvjrlpyzhioxuture/name }}
	HostName {{ op://5ebyeb4rgmu73mcoodmzro4kyu/sbpc6n3eorvjrlpyzhioxuture/URL }}
	User {{ op://5ebyeb4rgmu73mcoodmzro4kyu/sbpc6n3eorvjrlpyzhioxuture/username }}
	IdentityAgent "~/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"

Host {{ op://5ebyeb4rgmu73mcoodmzro4kyu/exely6m4mmyhfy5chd7se7ph5a/name }}
	HostName {{ op://5ebyeb4rgmu73mcoodmzro4kyu/exely6m4mmyhfy5chd7se7ph5a/URL }}
	User {{ op://5ebyeb4rgmu73mcoodmzro4kyu/exely6m4mmyhfy5chd7se7ph5a/username }}
	Port {{ op://5ebyeb4rgmu73mcoodmzro4kyu/exely6m4mmyhfy5chd7se7ph5a/port }}
	IdentityAgent "~/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"
