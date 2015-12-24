"""
Support for debugging

N.b. can't go in utils.py as utils is imported be eups, and we need to import eups.Eups here
"""
from __future__ import print_function
import re, sys
import eups.Eups    

def parseDebugOption(debugOpts):
    """Parse the options passed on the command line as --debug=..."""
    allowedDebugOptions = ["", "debug", "profile([filename])", "raise"]

    debugOptions = re.split("[:,]", debugOpts)
    for do in debugOptions:
        if not do in allowedDebugOptions and not re.search(r"^profile($|\[)", do):
            print("Unknown debug option: %s; exiting (valid options are: %s)" % \
                (do, ", ".join([x for x in allowedDebugOptions if x])), file=sys.stderr)
            sys.exit(1)
    # n.b. these may be reset later in a cmdHook
    eups.Eups.debugFlag = "debug" in debugOptions
    eups.Eups.allowRaise = "raise" in debugOptions
    eups.Eups.profile = False
    for o in debugOptions:
        mat = re.search(r"^profile(?:\[([^]]*)])?", o)
        if mat:
            eups.Eups.profile = mat.group(1)
            if not eups.Eups.profile:
                eups.Eups.profile = "eups.prof"
