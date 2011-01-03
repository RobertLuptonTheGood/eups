#!/usr/bin/env python
"""
A master script for running all tests.
"""
import unittest
from testServerLocal import *
from testServerWeb import *
from testServerSsh import *

if __name__ == "__main__":
    unittest.main()
