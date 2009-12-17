import os 

testEupsStack = os.environ["PWD"]

if os.path.isdir("python") and os.path.isdir("tests") and \
   os.path.isfile("Release_Notes"):

    # we're in the main build directory
    os.environ["EUPS_DIR"] = os.environ["PWD"]
    testEupsStack = os.path.join(os.environ["PWD"], "tests")

elif os.path.isdir("ups_dir") and os.path.isdir("testserver") and \
     os.path.isfile("testAll.py"):

    # we're in the test directory
    os.environ["EUPS_DIR"] = os.path.dirname(os.environ["PWD"])


