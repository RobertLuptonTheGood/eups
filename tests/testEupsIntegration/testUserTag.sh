#!/bin/bash
#
# Test that user tags are retained across invocations of setups.sh
# This test was motivated by issue #93
#
set -e

_assert()
{
	# usage: assert <command_to_run> <expected_output>

	RET=$($1)
	if [[ "$RET" != "$2" ]]; then
		echo "Unexpected output of \`$1\`: '$RET' != '$2' (at line ${BASH_LINENO[0]})"
		exit -1
	fi
}

source "$EUPS_DIR/bin/setups.sh"

# Prepare the dummy stack
FLAV="$(eups flavor)"
rm -rf tmpstack
cp -a stack.testUserTag tmpstack
mv tmpstack/FLAVOR "tmpstack/$FLAV"

# Declare our product with the user tag
_undeclare()
{
	eups undeclare prod tag:$USER
	rm -rf tmpstack
}
export EUPS_PATH="$PWD/tmpstack"
trap _undeclare EXIT
eups declare -r "$EUPS_PATH/$FLAV/prod/a" -t $USER prod
_assert "eups list --raw" "prod|tag:$USER|$USER"

# Reload EUPS and check that the user tag is still there
source "$EUPS_DIR/bin/setups.sh"
_assert "eups list --raw" "prod|tag:$USER|$USER"
