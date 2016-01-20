#!/bin/bash
set -e

source "$EUPS_DIR/bin/setups.sh"

cd cfitsio

touch .tap_package
touch blah

eupspkg -e fetch
eupspkg -e prep
