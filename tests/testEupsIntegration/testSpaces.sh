#!/bin/bash -e
#
# Verify that setup/unsetup works in a local directory with a space
# in the path. Also attempts to unsetup eups itself.
#

testpath="`pwd`/space path"
trap '{ rm -rf "$testpath"; }' EXIT
rm -rf "$testpath"

# Create dummy EUPS package with empty table file
mkdir "$testpath"
mkdir "$testpath/ups"
touch "$testpath/ups/spaces.table"

# Initialize EUPS
source "$EUPS_DIR/bin/setups.sh"

cd "$testpath"

setup -k -r .
if [ $(eups list 2>&1 | grep -c Problem) != "0" ]; then
  echo Problem detected in eups list
  exit 1
fi

unsetup -r .
unsetup eups

