#!/bin/bash
set -e

source "$EUPS_DIR/bin/setups.sh"

cd "space path"

setup -k -r .
if [ $(eups list 2>&1 | grep -c Problem) != "0" ]; then
  echo Problem detected in eups list
  exit 1
fi

unsetup -r .
unsetup eups
