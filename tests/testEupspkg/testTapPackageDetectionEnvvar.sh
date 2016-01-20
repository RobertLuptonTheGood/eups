#!/bin/bash
set -e

source "$EUPS_DIR/bin/setups.sh"

cd cfitsio

echo "TAP_PACKAGE=1" >> ups/eupspkg.cfg.sh
touch blah

eupspkg -e fetch
eupspkg -e prep
