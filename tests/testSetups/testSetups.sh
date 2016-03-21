#!/bin/bash -xe
#
# The test code. Return nonzero in case of problems.
#

# Test in a clean environment
unset DYLD_LIBRARY_PATH

source "$EUPS_DIR/bin/setups.sh"

eups list
