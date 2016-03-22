#!/bin/bash -xe
#
# A script that installs and tests EUPS on TravisCI
#

# Should we test with csh installed?
if [[ $CI_WITH_CSH == 1 ]]; then
	sudo apt-get install -y csh
fi

# configure
PREFIX=$(mktemp -d -t "eupstest XXXXXX")
./configure --prefix="$PREFIX" --with-python=$(which python)

# build, test, and install
make
make tests
make install
