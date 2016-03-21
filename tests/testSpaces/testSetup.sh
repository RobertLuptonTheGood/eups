#!/bin/bash
set -e

source "$EUPS_DIR/bin/setups.sh"

cd "space path"

setup -k -r .
unsetup -r .
