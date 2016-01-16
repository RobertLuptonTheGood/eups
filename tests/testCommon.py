import os, sys, unittest

testEupsStack = os.path.dirname(__file__)
os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)

# clear out any products setup in the environment as these can interfere 
# with the tests
setupvars = filter(lambda k: k.startswith('SETUP_'), os.environ.keys())
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

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def findFileFromRoot(ifile):
    """Find file which is specified as a path relative to the toplevel directory;
    we start in $cwd and walk up until we find the file (or throw IOError if it doesn't exist)

    This is useful for running tests that may be run from <dir>/tests or <dir>"""
    
    if os.path.isfile(ifile):
        return ifile

    ofile = None
    file = ifile
    while file != "":
        dirname, basename = os.path.split(file)
        if ofile:
            ofile = os.path.join(basename, ofile)
        else:
            ofile = basename

        if os.path.isfile(ofile):
            return ofile

        file = dirname

    raise IOError("Can't find %s" % ifile)
