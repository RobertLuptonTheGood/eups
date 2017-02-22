#!/bin/bash

LASTVER=$(git describe --abbrev=0 --match "[0-9]*")

cat <<EOF
New version release script
==========================

This script will ask you for the new version number, and open the
Release_Notes so you can add a short description of what's changed since the
last release.

It will record the new release number to git.version, commit everything, and
tag the source with the version number (an annotated tag).


                     Last released version: $LASTVER
EOF

read -e -p "Enter the new version string (e.g., 1.2.3): " VERSION

if ! [[ "$VERSION" =~ ^[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$ ]]; then
	echo
	echo "warning: the version doesn't conform to the customary X.Y.Z format."
	read -p "Are you sure you want to continue (y/n)? " -r
	[[ ! $REPLY =~ ^[Yy]$ ]] && exit -1
fi

# Prepare proposed delease notes
rm -f Release_Notes.tmp
cat > Release_Notes.tmp  <<-EOT
	# Below are the draft release notes, derived from git commit history
	# since the last release. Please edit them to emphasize major new
	# features, and remove unnecessary clutter.
	#
	# All lines beginning with '#' are considered to be comments and
	# will be stripped.

EOT
echo "$(date "+%Y-%m-%d") $USER ($VERSION)" >> Release_Notes.tmp
git log --first-parent --oneline $LASTVER.. | cut -d' ' -f 2- | sed 's/^/    - /' >> Release_Notes.tmp
echo >> Release_Notes.tmp
echo "    dev stats:" >> Release_Notes.tmp
echo "      -$(git diff --shortstat $LASTVER)" >> Release_Notes.tmp
echo -n "      - contributors: " >> Release_Notes.tmp
git shortlog -ns --no-merges $LASTVER..HEAD | cut -d$'\t' -f 2 | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/, /g' >> Release_Notes.tmp
echo "#" >> Release_Notes.tmp
echo "#" >> Release_Notes.tmp
echo "#" >> Release_Notes.tmp
echo >> Release_Notes.tmp
cat Release_Notes >> Release_Notes.tmp

"${EDITOR:-vi}" Release_Notes.tmp

# Delete all leading blank lines at top of file (only). Also delete comment lines.
grep -v '^#' Release_Notes.tmp | sed '/./,$!d' > Release_Notes

echo "$VERSION" > git.version

git commit -a -m "Releasing version $VERSION"
git tag -a -m "Version $VERSION" "$VERSION"

cat <<EOF
Make sure to run:

   git push
   git push --tags

to push the changes upstream.
EOF
