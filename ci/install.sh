#!/bin/bash -xe
#
# A script to setup the Travis build environment with Miniconda
#

MARKER=.installed

# Exit if already exists (restored from cache)
test -f "$HOME/miniconda/$MARKER" && exit;

# Install Python 2.7 Miniconda
rm -rf "$HOME/miniconda"
curl -L -O https://repo.continuum.io/miniconda/Miniconda-latest-Linux-x86_64.sh
bash Miniconda-latest-Linux-x86_64.sh -b -p "$HOME/miniconda"
export PATH="$HOME/miniconda/bin:$PATH"
	
# Install Python 3.5 environment
conda create --yes -n py35 "python=3.5.*"

# Install Python 2.6 environment
conda create --yes -n py26 "python=2.6.*"

touch "$HOME/miniconda/$MARKER"
