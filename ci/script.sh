#!/bin/bash -xe
#
# A script that installs and tests EUPS on TravisCI
#

# configure
PREFIX=$(mktemp -d -t "eupstest XXXXXX")
./configure --prefix="$PREFIX" --with-python=$(command -v python)

# build, test, and install
make
make tests
make install
