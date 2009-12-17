#!/usr/bin/env python
"""
A master script for running all tests.
"""
import unittest
from testTags import *
from testProduct import *
from testDb import *
from testStack import *
from testTable import *
from testEups import *
from testCmd import *
from testDeprecated import *
from testApp import *

if __name__ == "__main__":
    unittest.main()
