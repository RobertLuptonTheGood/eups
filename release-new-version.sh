#!/bin/bash

cat <<EOF
New version release script
==========================

This script will ask you for the new version number, and open the
Release_Notes so you can add a short description of what's changed since the
last release.

It will record the new release number to git.version, commit everything, and
tag the source with the version number (a signed tag).


                     Last released version: $(git describe --abbrev=0 --match "[0-9]*")
EOF

read -e -p "Enter the new version string (e.g., 1.2.3): " VERSION

if ! [[ "$VERSION" =~ ^[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$ ]]; then
	echo
	echo "warning: the version doesn't conform to the customary X.Y.Z format."
	read -p "Are you sure you want to continue (y/n)? " -r
	[[ ! $REPLY =~ ^[Yy]$ ]] && exit -1
fi

"${EDITOR:-vi}" Release_Notes

echo "$VERSION" > git.version

git commit -a -m "Releasing version $VERSION"
git tag -a -m "Version $VERSION" "$VERSION"

cat <<EOF
Make sure to run:

   git push
   git push --tags

to push the changes upstream.
EOF
