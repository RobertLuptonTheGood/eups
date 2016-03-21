#!/usr/bin/env python
"""
Test that running setups.{sh|csh} works as expected.
"""

import testCommon

EupsIntegrationTest = testCommon.ScriptTestSuite("testEupsIntegration")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        EupsIntegrationTest,
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
