#!/bin/bash -xe
#
# A script that tests EUPS on TravisCI with Miniconda
#

# Should we test with csh installed?
if [[ $CI_WITH_CSH == 1 ]]; then
	sudo apt-get install -y csh
fi

make_and_install()
{
	(
		# configure
		PREFIX=$(mktemp -d -t "eupstest XXXXXX")

		./configure --prefix="$PREFIX" --with-python=$(which python)

		# install & test
		make
		make tests
		make install

		# cleanup
		chmod -R +w "$PREFIX"
		rm -rf "$PREFIX"
	)
}

# Python 2.7
make_and_install

# Python 2.6
source activate py26
make_and_install

# Python 3.5
source activate py35
make_and_install
