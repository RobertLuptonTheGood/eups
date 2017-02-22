This directory contains unit test scripts and related test data.

There are three main test scripts:

   testAll.py          master script of tests that can be run without a
                         network connection
   testServerAll.py    master script for tests of "eups distrib"; some
                         tests require access to http://dev.lsstcorp.org/
   testServerLSST.py   LSST-specific "eups distrib" tests

To run the non-network tests, type:

   python tests/testAll.py

==========================================================================

Adding New Tests
--------------------------------------------------------------------------

The test scripts use the standard Python unittest module.  The tests
are segregated into separate files according to the module being
tested (e.g. testDb.py tests stuff in eups.db).  Each test file (that
doesn't require the network) gets imported into the master script,
testAll.py.  Tests that require the network (that is, tests of "eups
distrib" functionality) get imported into testServerAll.py.

New tests can be placed into the appropriate module test file, or it
can be placed into testMisc.py.  The new tests will get run
automatically as part of testAll.py (or testServerAll.py).  To create
a new test file, one can use testMisc.py as a template.  To have the
new test file's tests run automatically, add an appropriate import
line to the master testAll.py script.  Setting the python variable
"__all__" inside the new test script to the list of unittest.TestCase
class defined in the file makes the import simple.


