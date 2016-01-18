#!/bin/bash -xe
#
# A script that tests EUPS on TravisCI with Miniconda
#

make_and_install()
{
	(
		PREFIX=$(mktemp -d -t XXXX)

		# install
		./configure --prefix="$PREFIX" --with-python=$(which python)
		make
		make install

		# run tests
		cd tests
		source $PREFIX/bin/setups.sh
		python testAll.py
	
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
