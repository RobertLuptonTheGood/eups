#!/bin/bash -- just to enable syntax highlighting --
#
# A simple unit test library for bash scripts. Example of how to include it
# in your scripts:
#
# if [[ "$RUN_UNIT" == 1 ]]; then
#
#	. "$EUPS_DIR/lib/bunit.sh"
#
#	ut1 "unit tests for _earliest_version()"
#	ut "_earliest_version 1.1 1.1.0"   == "1.1"
#	ut "_earliest_version 1.1.0 1.1.0" == "1.1.0"
#	ut "_earliest_version 1.2.3 1.2.2" == "1.2.2"
#
#  fi

################ ---- PROGRESS REPORTING HELPERS ---- #################

ut0()
{
	# print a prefix for a unit test, to stderr

	local STR="$@"
	printf "%-45s : " "$STR" 1>&2
}

ut1()
{
	# print a heading for a group of unit tests, to stderr

	local STR="$@"
	echo "======== $STR ========" 1>&2
}

##################### ---- UNIT TEST HELPERS ---- #####################

ut()
{
	# usage: ut <code_to_evaluate> <op> <expected_result>
	#
	# evals code in $1 and uses $2 to compare it to $3

	eval RES="$($1)"
	if [ "$RES" $2 "$3" ]; then
		echo "\$($1) $2 '$3': ok."
	else
		echo "\$($1) $2 '$3': FAILED (lhs: $RES)."
		_UT_FAIL=1
	fi
}

ut_exit()
{
	# check if any unit test failed, exit if so

	if [[ ! -z $_UT_FAIL ]]; then
		echo '****' error: some unit tests failed.
		exit -1
	else
		echo all unit tests passed.
		exit 0
	fi
}

