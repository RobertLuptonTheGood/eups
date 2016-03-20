#!/bin/csh -xe
#
# The test code. Return nonzero in case of problems.
#

# Test in a clean environment
unsetenv DYLD_LIBRARY_PATH

source "$EUPS_DIR/bin/setups.csh"

eups list
