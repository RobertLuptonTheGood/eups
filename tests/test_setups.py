#!/usr/bin/env python
"""
Test that running setups.{sh|csh} works as expected.
"""

import testCommon

SetupsTest = testCommon.ScriptTestSuite("testSetups")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        SetupsTest,
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
