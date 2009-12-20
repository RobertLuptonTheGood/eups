This directory contains unit test scripts and related test data.  

There are three main test scripts:

   testAll.py          master script of tests that can be run without a
                         network connection
   testServerAll.py    master script for tests of "eups distrib"; some 
                         tests require access to http://dev.lsstcorp.org/
   testServerLSST.py   LSST-specific "eups distrib" tests

To run the non-network tests, type:

   python tests/testAll.py

