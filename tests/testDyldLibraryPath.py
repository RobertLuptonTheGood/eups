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

sh_test = """\
export DYLD_LIBRARY_PATH=%s
echo $DYLD_LIBRARY_PATH

source ../bin/setups.sh

setup dyldtest -r . -m dyldtest.table
echo $DYLD_LIBRARY_PATH

unsetup dyldtest
echo $DYLD_LIBRARY_PATH
""";

csh_test = """\
setenv DYLD_LIBRARY_PATH %s
echo $DYLD_LIBRARY_PATH

source ../bin/setups.csh

setup dyldtest -r . -m dyldtest.table
echo $DYLD_LIBRARY_PATH

unsetup dyldtest
echo $DYLD_LIBRARY_PATH
""";

class DyldLibraryPath(unittest.TestCase):

    def setUp(self):
        # remove any SETUP_ variables from the environment
        # as well as EUPS_DIR
        self.env = os.environ.copy()

        for key in self.env.keys():
            if key.startswith('SETUP_'):
                del self.env[key]

        self.env.pop('EUPS_DIR', None)

    def tearDown(self):
        pass

    def _run_script(self, shell, cmds, expect):
        # Run script in the cleaned-up environment
        try:
            output = subprocess.check_output([shell, '-c', cmds], stderr=subprocess.STDOUT, env=self.env)
        except subprocess.CalledProcessError as e:
            args_str = ', '.join([ "%s=%s" % (k, v) for (k, v) in args.items()])
            self.fail("Failed to run test for shell %s with args={%s}.\nretcode=%s\noutput: %s" % (shell, args_str, e.returncode, e.output))

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
