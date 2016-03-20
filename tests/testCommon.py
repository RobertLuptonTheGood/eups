import os, sys, unittest
import os.path
import subprocess
import glob

# This will activate Python 2.6 compatibility hacks
if sys.version_info[:2] == (2, 6):
	import python26compat

testEupsStack = os.path.dirname(__file__)

# clear out any products setup in the environment as these can interfere 
# with the tests
setupvars = [k for k in os.environ.keys() if k.startswith('SETUP_')]
for var in setupvars:
    del os.environ[var]

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Support code for running unit tests implemented as bash scripts
#
#

def ScriptTestSuite(testSuiteDir):
    """
        A class factory for running a directory full of bash scripts as
        a Python.unittest test suite. For example, assuming we have a
        directory `foo/`, with scripts `testA.sh` and `testB.sh`, the
        following:

            FooTest = testCommon.ScriptTestSuite("foo")

        will construct a class with members `testA()` and `testB()`, where
        each one will run their corresponding script and fail if it returns
        a non-zero exit code. A full-fledged example can be found in
        testEupspkg.py

        Notes:
          - The given subdirectory is scanned for all files matching
            test*, and a test method is created for each one. Files
            ending in '~' are skipped (these are usually editor backups)
          - if `setup.sh` or `teardown.sh` exist, they will be run from the
            corresponding setUp() and tearDown() unittest methods
          - Scripts must return non-zero exit code to signal failure
          - All scripts must be executable, and begin with an apropriate
            shebang. This class doesn't introspect them in any way, so it's
            theoretically possible to (e.g.) write the tests in Ruby
          - By convention, end shell scripts with .sh and .csh, depending on
            the interpreter used.
          - By convention, use the same name for the Python test file, and
            the subdirectory with the bash scripts (e.g., testEupspkg.py
            should execute scripts in testEupspkg/)
    """
    def setUp(self):
        # chdir into the directory with the scripts
        self.initialDir = os.path.abspath(".")
        os.chdir(self.testDir)

        # Make sure the scripts know to find EUPS
        if "EUPS_DIR" not in os.environ:
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)

        # run setup.sh if it exists
        if os.path.isfile("setup.sh"):
            subprocess.check_call("./setup.sh")

    def tearDown(self):
        # run teardown.sh if it exists
        if os.path.isfile("teardown.sh"):
            subprocess.check_call("./teardown.sh")

        # return back to the directory we started from
        os.chdir(self.initialDir)

    def runBashTest(self, testFn):
        try:
            output = subprocess.check_output(testFn, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            self.fail(("Test %s failed (retcode=%s)\nscript: %s\noutput: " + "-"*65 + "\n%s" + "-"*73) % (testFn, e.returncode, testFn, e.output))

    testDir = os.path.join(os.path.abspath(os.path.dirname(__file__)), testSuiteDir)

    class_members = {
        "testDir": testDir,
        "setUp": setUp,
        "tearDown": tearDown,
        "runBashTest": runBashTest,
    }

    # Discover all tests -- executable files beginning with test
    for testFn in glob.glob(os.path.join(testDir, "test*")):
        if not os.access(testFn, os.X_OK) or testFn.endswith("~"):
            continue
        methodName = os.path.basename(testFn).replace('.', '_')
        class_members[methodName] = lambda self, testFn=testFn: runBashTest(self, testFn)

    return type(testSuiteDir, (unittest.TestCase,), class_members)


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
