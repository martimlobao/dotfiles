# Martim's dotfiles

![Screenshot of my shell prompt](https://i.imgur.com/3AroNRu.png)

This repository contains my personal dotfiles, as well as several scripts to install applications and configure settings. Although the bash configuration settings should (mostly) work on any Unix-based system, most of these scripts were only designed to run on macOS and likely won't run at all on any other OS.

Here's a short description of each script in this repository:

- `local.sh` _interactively_ configure local settings unique to each machine, like the computer name and your git user details
- `macos.sh` configure several macOS settings
- `brew.sh` install command-line tools using Homebrew
- `apps.sh` install fonts and macOS apps using Homebrew and Mac App Store
- `dock.sh` configure macOS dock
- `bootstrap.sh` install dotfiles for bash settings and command line layout
- `setup.sh` install Homebrew, run all scripts, and install private dotfiles from private repository

**Attention:** Running these dotfiles blindly will overwrite settings and install apps and fonts that you probably don't need. Some care was taken to not overwrite non-transferable settings (e.g. [git user settings](https://github.com/martimlobao/dotfiles/blob/master/local.sh)), but unless your preferences are identical to mine, you should [fork this repository](https://github.com/martimlobao/dotfiles/fork), review the code, and remove things you don't want or need. Use at your own risk!

## Installation

**Note:** If you fork this repository to create your own dotfiles, replace `https://git.io/dotinstall` with `https://github.com/<USER>/<REPO>/tarball/master` in the commands below.

### Fresh install

To download these dotfiles on a new Mac (without git):

```bash
curl -L https://git.io/dotinstall | tar -xz
```

Then, open the downloaded folder and run `setup.sh`, `bootstrap.sh`, or any other script:

```bash
cd martim*
./local.sh
```

### One-line everything install

To run everything in a single command:

```bash
curl -L https://git.io/dotinstall | tar -xz; cd martim*; ./setup.sh
```

**Warning:** This will overwrite settings, any existing dotfiles in your home directory, and install apps and fonts. Don't run this unless you're me or you have my exact preferences!

### One-line dotfiles install

To _only_ install dotfiles without needing to install git or run any scripts:

```bash
cd; curl -L https://git.io/dotinstall | tar -xzv --strip-components 1 --exclude={*.sh,*.md}
```

**Warning:** This will overwrite any existing dotfiles in your home directory.

### Terminal-free install!

Go to [git.io/dotinstall](https://git.io/dotinstall) and open the downloaded file, then double-click on a script to run it.

## Usage

Most of these scripts rely on [Homebrew](https://brew.sh/), which is installed when running `setup.sh`. However, if you don't want to install everything in this repository, you can choose to install Homebrew by itself and pick and choose what you like:

```bash
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

## Contributing

[Pull requests](https://github.com/martimlobao/dotfiles/pulls) are welcome. For non-minor changes, consider [opening an issue](https://github.com/martimlobao/dotfiles/issues) first to discuss what you would like to change.

Note that these are my personal dotfiles, so if you'd like to customize them to your own taste, it might make more sense to [fork this repository](https://github.com/martimlobao/dotfiles/fork) instead.

## Thanks

- [@mathiasbyens](https://mathiasbynens.be/) for his [dotfiles repository](https://github.com/mathiasbynens/dotfiles), off of which this repository was based
- [@kennethreitz](https://www.kennethreitz.org/) for a few [functions and inspiration](https://github.com/kennethreitz/dotfiles)
- [@kevinsuttle](https://kevinsuttle.com/) for a great compilation of [macOS defaults](https://github.com/kevinSuttle/macOS-Defaults)
- [@coreyschafer](https://coreyms.com/) for his awesome [YouTube tutorials](https://www.youtube.com/user/schafer5) on multiple topics
- [@henriquebastos](https://henriquebastos.net/) for [documentation](https://medium.com/@henriquebastos/the-definitive-guide-to-setup-my-python-workspace-628d68552e14) on getting Jupyter to run nicely with pyenv
- [@ryanpavlick](https://github.com/rpavlick) for his [macOS dock customization functions](https://github.com/rpavlick/add_to_dock)
