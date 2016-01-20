import os, sys, unittest

testEupsStack = os.path.dirname(__file__)

# clear out any products setup in the environment as these can interfere 
# with the tests
setupvars = [k for k in os.environ.keys() if k.startswith('SETUP_')]
for var in setupvars:
    del os.environ[var]

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Support code for running unit tests
#

def makeSuite(testCases, makeSuite=True):
    """Returns a list of all the test suites in testCases (a list of object types); if makeSuite is True,
    return a unittest suite"""

    tests = []
    for t in testCases:
        tests += unittest.makeSuite(t)

    if makeSuite:
        return unittest.TestSuite(tests)
    else:
        return tests

def run(suite, exit=True):
    """Exit with the status code resulting from running the provided test suite"""

    if unittest.TextTestRunner().run(suite).wasSuccessful():
        status = 0
    else:
        status = 1

    if exit:
        sys.exit(status)
    else:
        return status
