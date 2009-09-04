"""
Utility functions used across EUPS classes.
"""
import time

def ctimeTZ(t=None):
    """Return a string-formatted timestampe with time zone"""

    if not t:
        t = time.localtime()

    return time.strftime("%Y/%m/%d %H:%M:%S %Z", t)

def isRealFilename(filename):
    """
    Return True iff "filename" is a real filename, not a placeholder.  
    It need not exist.  The following names are considered placeholders:
    ["none", "???"].
    """

    if filename is None:
        return False
    elif filename in ("none", "???"):
        return False
    else:
        return True
    
