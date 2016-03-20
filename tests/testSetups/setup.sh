#!/bin/bash

# Test if we should skip tests that depend on csh
rm -f *.skip
if [[ ! -x /bin/csh ]]; then
	for TEST in *.csh; do
		echo "No /bin/csh on this system." >> "$TEST.skip"
	done
fi
