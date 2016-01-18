This directory contains helper scripts for continuous integration. It is
primarily meant to be used with TravisCI, but script.sh can also be used
locally if you have Miniconda and the right environments set up.

Available scripts:
* install.sh -- will install miniconda to $HOME/miniconda, and create
  environments with different versions of Python
* script.sh -- will configure/make/make install and then run the tests
