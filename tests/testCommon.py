import os 

testEupsStack = os.environ["PWD"]

if os.path.isdir("python") and os.path.isdir("tests") and \
   os.path.isfile("Release_Notes"):

    # we're in the main build directory
    testEupsStack = os.path.join(os.environ["PWD"], "tests")


