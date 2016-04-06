#!/bin/bash -e
#
# Verify that DYLD_LIBRARY_PATH gets propagatd through `setup`
# both with bash and csh. This is an issue due to System Integrity
# Protection on OS X 10.11.
#

trap '{ rm -f auxTestDyldLibraryPath_csh dyldtest.table; }' EXIT

DYLDTEST_PATH="/foo/bar"

cat > dyldtest.table <<-EOT
envPrepend(DYLD_LIBRARY_PATH, "$DYLDTEST_PATH")
EOT

# Test function for bash
auxTestDyldLibraryPath_bash()
{
	echo "bash: testing with DYLD_LIBRARY_PATH=$1"

	if [[ -z "$@" ]]; then
		unset DYLD_LIBRARY_PATH
		EXPECT="$DYLDTEST_PATH"
	else
		export DYLD_LIBRARY_PATH="$@"
		EXPECT="$DYLDTEST_PATH:$@"
	fi

	. "$EUPS_DIR/bin/setups.sh" 2>/dev/null
	export EUPS_PATH="$PWD/.."		# To silence warnings about inexistent ups_db

	setup dyldtest -r . -m dyldtest.table
	echo "    '$DYLD_LIBRARY_PATH' (expecting: '$EXPECT')"
	[[ "$DYLD_LIBRARY_PATH" == "$EXPECT" ]] || exit -1

	unsetup dyldtest
	echo "    '$DYLD_LIBRARY_PATH' (expecting: '$1')"
	[[ "$DYLD_LIBRARY_PATH" == "$@" ]] || exit -1
}

# Write out the csh variant, if csh is present on the system (else just link to /bin/true, so the test doesn't fail)
rm -f auxTestDyldLibraryPath_csh
! type /bin/csh >/dev/null 2>&1 && echo "#!/bin/sh" > auxTestDyldLibraryPath_csh || cat > auxTestDyldLibraryPath_csh <<-EOT
	#!/bin/csh -e

	echo "csh: testing with DYLD_LIBRARY_PATH=\$1"

	if(\$#argv == 0) then
	    unsetenv DYLD_LIBRARY_PATH
	    set EXPECT="$DYLDTEST_PATH"
	else
	    setenv DYLD_LIBRARY_PATH "\$1"
	    set EXPECT="$DYLDTEST_PATH:\$1"
	endif

	source "\$EUPS_DIR/bin/setups.csh" >& /dev/null
	setenv EUPS_PATH "`pwd`/.."

	setup dyldtest -r . -m dyldtest.table
	echo "    '\$DYLD_LIBRARY_PATH' (expecting: '\$EXPECT')"
	test "\$DYLD_LIBRARY_PATH" = "\$EXPECT" || exit -1

	unsetup dyldtest
	echo "    '\$DYLD_LIBRARY_PATH' (expecting: '\$1')"
	test "\$DYLD_LIBRARY_PATH" = "\$1" || exit -1
EOT
chmod +x auxTestDyldLibraryPath_csh

# Test with empty DYLD_LIBRARY_PATH
(   auxTestDyldLibraryPath_bash )
( ./auxTestDyldLibraryPath_csh )

# Test with regular DYLD_LIBRARY_PATH
(   auxTestDyldLibraryPath_bash "a/b/c" )
( ./auxTestDyldLibraryPath_csh  "a/b/c" )

# Test with spaces in input DYLD_LIBRARY_PATH
( auxTestDyldLibraryPath_bash  "a/b c/d" )
( ./auxTestDyldLibraryPath_csh "a/b c/d" )
