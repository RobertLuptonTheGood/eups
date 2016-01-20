#!/usr/bin/env python
"""
Test if DYLD_LIBRARY_PATH is retained after setup is run. This is trivial
everywhere except on OS X 10.11 (and higher, presumably), where System
Integrity Protection wipes out DYLD_LIBRARY_PATH whenever an executable from
/usr/bin or /bin is run.
"""
import os, os.path
import unittest
import subprocess
import testCommon
from testCommon import testEupsStack

sh_test = """\
export DYLD_LIBRARY_PATH=%s
echo $DYLD_LIBRARY_PATH

. $EUPS_DIR/bin/setups.sh

setup dyldtest -r . -m dyldtest.table
echo $DYLD_LIBRARY_PATH

unsetup dyldtest
echo $DYLD_LIBRARY_PATH
""";

csh_test = """\
setenv DYLD_LIBRARY_PATH %s
echo $DYLD_LIBRARY_PATH

source $EUPS_DIR/bin/setups.csh

setup dyldtest -r . -m dyldtest.table
echo $DYLD_LIBRARY_PATH

unsetup dyldtest
echo $DYLD_LIBRARY_PATH
""";

TestDir = os.path.abspath(os.path.dirname(__file__))

class DyldLibraryPath(unittest.TestCase):

    def setUp(self):
        self.initialDir = os.path.abspath(".")
        os.chdir(TestDir)

        self.env = os.environ.copy()
        if "EUPS_DIR" not in self.env:
            self.env["EUPS_DIR"] = os.path.dirname(testEupsStack)

    def tearDown(self):
        os.chdir(self.initialDir)

    def _run_script(self, shell, cmds, expect):
        # Run script in the cleaned-up environment
        try:
            output = subprocess.check_output([shell, '-c', cmds], stderr=subprocess.STDOUT, env=self.env, universal_newlines=True)
        except subprocess.CalledProcessError as e:
            self.fail("Failed to run test for shell %s with args={%s}.\nretcode=%s\noutput: %s" % (shell, cmds, e.returncode, e.output))

        self.assertEqual(output, expect)

    def testDyldLibraryPathRetention_sh(self):
        self._run_script("/bin/sh", sh_test % 'a/b/c', "a/b/c\n/foo/bar:a/b/c\na/b/c\n")
        self._run_script("/bin/sh", sh_test % ''     , "\n/foo/bar\n\n")

    def testDyldLibraryPathRetention_csh(self):
        if os.path.exists("/bin/csh"):
            self._run_script("/bin/csh", csh_test % 'a/b/c', "a/b/c\n/foo/bar:a/b/c\na/b/c\n")
            self._run_script("/bin/csh", csh_test % ''     , "\n/foo/bar\n\n")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        DyldLibraryPath,
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
